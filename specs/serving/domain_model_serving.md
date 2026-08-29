# Domain-Model Serving

> Status: Draft v0.1. How the **biological foundation models** — AlphaGenome, Evo 2, ESMFold,
> Boltz-2, RFdiffusion, LigandMPNN, AlphaFold-style folding, SpliceAI, ChromBPNet, Orca, DNA
> shape predictors, docking/scoring, antiSMASH, InterProScan, etc. — are served behind the
> CellXP service boundary. Catalog: `documentation/reference/external_models_and_services.md`.
> Service interfaces: `specs/services/{alphagenome,structure,binding,crispr,reference,gwas}_service.md`.
> Job machinery: `specs/agent/control-flow/concurrency.md`. Distinct from
> `reasoning_llm_serving.md` (the agent's "brain").

## 1. Scope

Domain models are the *predictive oracles* the agent orchestrates. They share three operational
properties:

- **Heavy.** GPU-resident, multi-second to multi-minute per call (some hours).
- **Heterogeneous.** Different runtimes (PyTorch, JAX/Flax, TF, ONNX), VRAM footprints, and
  input shapes.
- **Compositional.** A single user turn typically chains several (e.g. variant resolution →
  variant scoring → folding → visualization).

The serving plane MUST accommodate this without leaking GPU/runtime details into harness adapters or
skill callers (`NFR-11`, `ADR-0003`, ADR-0008).

## 2. Architecture

```
       HarnessAdapter → CellXP skill/policy kernel
                 │
                 ▼  ServiceResult[T] over Service interface
       ┌──────────────────────┐
       │  Service in-process  │  ← light/CPU calls, validation, formatting
       │  (services/<name>/)  │
       └─────────┬────────────┘
                 │ heavy?  ──── yes ──► dispatch via job layer (Redis)
                 │                        │
                 │                        ▼
                 │             ┌─────────────────────────┐
                 │             │  GPU worker pool         │
                 │             │  (jobs/worker.py / gpu.py)│
                 │             │  per-model adapters       │
                 │             └─────────────────────────┘
                 │                        │
                 │                  emit step.* / activity.update / artifact.* events
                 │                        │
                 └────────────────────────┘
```

The harness never sees workers directly. Typed skills call services; services own the in-process
logic; **jobs** own the
GPU/heavy paths; the queue + checkpointed run state make liveness, retries, and reconnection
work uniformly (`control-flow/concurrency.md`, `streaming_protocol.md` §5).

## 3. Three deployment regimes

| Regime | Where models run | Trade-offs |
|---|---|---|
| **In-process (regime 1)** | services run model code in the API process; small models only (e.g. motif scan, splice score on CPU) | simplest; no IPC; blocks the API event loop for non-trivial work — keep operations short |
| **Local GPU worker (regime 2)** | dedicated worker process(es) on the same host; Redis dispatch; one or two GPUs | clean separation; survives API restart; models warm-loaded per worker process |
| **Worker pool / multi-GPU (regime 3)** | k8s `Deployment` per model class; HPA on Redis queue depth; per-model VRAM-aware scheduling | scales to many concurrent users / heavy compose chains |

The same service code dispatches the same job in all three regimes. The dispatch fence is "is
the operation heavy?" — defined per `services/<name>/spec` and configurable per deployment.

## 4. Runtime options per model class

CellXP does **not pick one inference framework** for everything. Different models ship with
different ergonomics; we use the right one per class and hide it behind the service interface.

| Model class | Recommended runtime | Why |
|---|---|---|
| **AlphaGenome / Evo 2 / DNA-LM heads** | model author's released runtime (often PyTorch or JAX) wrapped in a FastAPI worker | model-specific input handling; framework-native fast paths; OK to colocate sibling heads in one worker to amortize load |
| **ESMFold** | PyTorch worker; optional batching for many short proteins | mature, well-documented; HF endpoints possible as opt-in remote |
| **Boltz-2** | PyTorch worker; single-GPU per replica; consider Triton if many concurrent | high VRAM; sequence-dependent latency; needs strict admission control |
| **RFdiffusion / LigandMPNN** | PyTorch workers; ProteinMPNN and LigandMPNN are cheap, RFdiffusion is heavier; chain in same worker | inverse-design loops compose them tightly |
| **SpliceAI / ChromBPNet / Orca / DNA shape** | TF/PyTorch as released; can colocate on one GPU; small VRAM | lightweight relative to folding |
| **Docking / cheminformetric scoring** | CPU-mostly (AutoDock Vina, GNINA on GPU optional); RDKit in-process | well-served by classical tools; GPU optional |
| **antiSMASH / InterProScan / Prokka** | CPU pipelines; long-running but parallelizable; queue separately | not GPU; isolate so they don't starve GPU workers |
| **Generic acceleration server (optional)** | **NVIDIA Triton Inference Server** or **Ray Serve** for organizations that want one inference plane across many model classes | trades operational complexity for unified ops; not the default |

**General principle.** Default is "FastAPI worker per model class with HuggingFace / model-author
runtime"; Triton/Ray Serve is an opt-in when an org wants a unified inference plane. The agent
contract doesn't change.

## 5. Worker process model

```
worker process
 ├─ on start: lazy-load assigned models (warm-load on first request, cached forever)
 ├─ main loop: BLPOP redis queue → validate → run model → write payload to object store
 ├─ for each request:
 │     emit step.started → run inference → emit activity.update on liveness ticks
 │     → write artifact payload (content-addressed) → emit step.finished + artifact.updated
 └─ on shutdown (SIGTERM): drain in-flight jobs up to a grace window; requeue interrupted
```

- **Warm model.** Each worker owns one (or a small set of) models; the model stays resident.
  Spawning a fresh worker for every call is forbidden — it would defeat warm load.
- **One model per worker class** for VRAM-sensitive models (Boltz-2, large LMs); colocate small
  models on one worker (motif scan + ChromBPNet + ESMFold-small).
- **Concurrency per worker** is bounded by `WORKER_MAX_CONCURRENT_JOBS` (typically 1 for
  large GPU models; can be higher for batchable models).
- **Batching where it helps.** ESMFold-on-short-proteins and motif scans can batch; the worker
  may coalesce queued requests within a small time window. The agent does not know about
  batching; batching never reorders observable side effects.
- **Cancellation.** Cancelled runs (`run_lifecycle.md` §4) emit a cancel signal that the worker
  observes between micro-steps; in-flight model forward passes complete (we don't kill mid-CUDA
  unless absolutely necessary).

## 6. Queue & scheduling

- **Transport.** Redis Streams for durable jobs + acks (`Redis 7`, `architecture_overview.md` §6).
- **Queues per class.** `q:alphagenome`, `q:boltz2`, `q:esmfold`, `q:rfdiffusion`,
  `q:antismash`, `q:cpu_heavy`, `q:gpu_misc`. Each queue maps to a worker pool with known VRAM
  affinity. This prevents head-of-line blocking (a 30-min Boltz job behind a 30-s motif scan).
- **Priority.** Priority within a queue uses simple stream-time + a `priority` field
  (low/normal/high). Interactive runs (a user is actively waiting on this SSE stream) are
  marked high; background jobs (re-runs, bulk imports) marked low.
- **Admission control.** Per-queue concurrency caps and per-tenant queue caps (regime 3) to
  prevent one runaway run from starving the rest. Exceeded caps stay queued with `activity.update`
  reporting position.
- **Retries.** Service-defined: deterministic failures (validation, OOM) do NOT retry; transient
  failures (NCCL hiccup, network) retry with backoff up to a small cap. Retries emit a new
  `Step` (provenance is append-only).

## 7. GPU/Hardware sizing rules of thumb

These are starting points to avoid surprise — concrete capacity planning is a deployment
exercise.

| Model | Typical VRAM | Latency at default | Notes |
|---|---|---|---|
| Motif scan (CPU) | n/a | < 1 s small windows | trivially parallel |
| ChromBPNet / DNA shape | 4–8 GB | 1–10 s | colocatable |
| SpliceAI | 4 GB | 1–10 s | colocatable |
| AlphaGenome-class single-head | 8–24 GB | 5–60 s per variant batch | model-specific |
| Evo 2 | 16–80 GB depending on variant | 5–60 s | large; tensor parallel possible |
| ESMFold (small protein) | 16 GB | seconds | batches well |
| ESMFold (large protein) | 24–48 GB | tens of seconds | size-dependent |
| Boltz-2 | 24–80 GB | minutes | scales superlinearly with size |
| RFdiffusion | 16–40 GB | tens of seconds per design | batchable in groups |
| LigandMPNN | 8–16 GB | < 1 s per design | cheap downstream of RFdiffusion |

In regime 3, schedule **one model class per node-group** with VRAM headroom for the worst case;
use HPA on Redis queue depth, not CPU.

## 8. Inputs, outputs, and provenance

Workers receive **normalized inputs** that the service has already validated (alphabets,
coordinates, organism/assembly checks; `RGS-1`). They produce:

- a small structured **result summary** (returned over the queue as the `step.finished` event
  payload),
- a large **output payload** written to object storage and content-addressed
  (`provenance_model.md` §6, `object_storage.md`),
- one or more **artifact references** the service translates into `ArtifactRef` via the
  visualization service (`specs/services/visualization_service.md`).

Every worker call MUST emit a complete `Step` with `tool`, `tool_version` (model weights hash
or revision), `inputs`, `params`, `input_hash`, `output_hash`, timing
(`provenance_model.md` §4). Cache hits short-circuit the dispatch (`PROV-5`); the cache key is
`(tool, tool_version, params, input_hash)`.

## 9. Hosted / opt-in remote models

Some users may want hosted endpoints for selected models (e.g. an institution's AlphaGenome
endpoint, a HuggingFace Inference Endpoint, NVIDIA NIM). The service interface supports it
identically:

- `*_SERVICE_URL` env points the service at a remote HTTP endpoint instead of an in-process
  client (`architecture_overview.md` §4).
- The service still emits the same `Step`/`ArtifactRef` shapes; provenance records the remote
  endpoint's identifier in `tool_version`.
- Hosted use is an explicit, audit-logged configuration choice; private payloads sent off-host
  surface in the chat UI as a model-source chip (`chat_interface.md` §11).

## 10. Failure modes

- **OOM.** Worker emits a structured error; the service decides whether to retry on a larger
  pool (rare) or surface as unsupported / size-too-large (`AGS-4`, `STS-1`).
- **Model unavailable.** Worker process not registered for the requested model: service returns
  a recoverable `RunError` and the agent may try a fallback model (e.g. ESMFold instead of
  Boltz-2 when Boltz is unavailable) only if the routing policy says so.
- **Stuck job.** Per-job hard timeout; the worker kills its own subprocess and acks the job as
  failed. The supervisor never assumes a job is "still running" beyond its declared budget
  (`Budget`, `state_schema.md` §15).
- **Worker crash.** Job re-enqueued with retry counter; if retries exhausted, surfaces as
  `error.added`; partial run continues per `NFR-6`.
- **Cache integrity error.** Stored hash mismatch on object-store read → integrity error
  (`PROV-4`); the cache entry is poisoned and the call is re-run.

## 11. Observability

Per-call metrics: model, worker host, queue wait, model load wait (cold/warm), inference time,
output size, retries, cache hit/miss. Per-queue: depth, oldest-job age, concurrency saturation.
GPU: utilization, VRAM, temperature (deployment concern). All metrics are tagged with
`run_id` so a slow user run can be traced end-to-end.

## 12. Migration paths

- Regime 1 → 2: Promote heavy operations from in-process to the worker pool by toggling the
  service's `dispatch_mode` (config-only; no code change in the agent).
- Regime 2 → 3: Add per-class queues, replica counts, and per-tenant admission caps; provision
  GPU node groups; no agent change.
- Add a new model: write a new worker adapter, add the model to the registry, optionally add a
  capability route; the agent gets it via the existing service operation. No graph changes for
  most additions.

## 13. Requirements

- **DMS-1** Heavy domain-model operations MUST run on the job layer (Redis + workers), never
  inline in the API process (`STS-1`, `AGS-3`).
- **DMS-2** Every worker invocation MUST emit a `Step` with `tool`, `tool_version`, `inputs`,
  `params`, `input_hash`, `output_hash`, and timing (`PROV-1`).
- **DMS-3** Workers MUST hot-load assigned models on first use and keep them warm; per-request
  cold-load is forbidden in regimes 2 and 3.
- **DMS-4** Per-class queues MUST exist to prevent head-of-line blocking between heavy and
  light jobs (§6).
- **DMS-5** Cancellation MUST be cooperative; workers MUST observe cancel signals between
  micro-steps (`run_lifecycle.md` §4).
- **DMS-6** Deterministic model calls MUST be cached by `(tool, tool_version, params,
  input_hash)`; cache hits MUST still emit a `Step` marked as cache-backed (`PROV-5`).
- **DMS-7** Hosted/remote model use MUST be audit-logged and the model source MUST be surfaced
  in the UI before private payloads egress.
- **DMS-8** Adding or upgrading a model MUST be a service-level change behind the same
  operation signature; the agent graph MUST NOT need to change for most upgrades (`NFR-11`).
- **DMS-9** Worker shutdown MUST drain in-flight jobs within a grace window and requeue
  interrupted work; in-flight runs MUST be resumable from checkpoints.

## 14. Open questions

- Whether to default to **Triton/Ray Serve** at regime 3 or stay with FastAPI workers.
- How to formalize **per-tenant GPU budgets** in regime 3 (quotas vs. credits vs. queues).
- Whether the cache layer is **per-deployment** or shared across deployments (CAS dedupe scope,
  `object_storage.md` §9.1).
- Live-batching for AlphaGenome variants from concurrent runs: worth it, or too much
  cross-tenant coupling?

## 15. Related

`specs/services/{alphagenome,structure,binding,crispr,reference,gwas,origami}_service.md` ·
`specs/agent/control-flow/concurrency.md` · `specs/agent/control-flow/run_lifecycle.md` ·
`specs/data/object_storage.md` · `specs/data/provenance_model.md` ·
`documentation/reference/external_models_and_services.md` ·
`documentation/explanation/architecture_overview.md` §5.1, §7.
