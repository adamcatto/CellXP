# Serving Specs

How CellXP is **served**: where each component runs, how requests are dispatched, how scaling
and replication work, and what the deployment topologies look like (local laptop → workstation
→ cluster → cloud multi-tenant). The data, services, agent, and interface specs say *what*
must be true; these specs say *where it runs and how it scales*.

CellXP is **local-first by default** (`mission.md`, `NFR-7`): a single workstation must be
able to run the whole stack against private sequence data with no third-party dependency. The
serving plane is therefore designed so the same code paths work in three regimes without
changes to the agent / service / interface contracts:

1. **Single-user local** — Postgres + Redis + Ollama + in-process services on one machine.
2. **Workstation / lab server** — adds GPU workers (Boltz/ESMFold), an object-store backend
   (MinIO / S3), and a separate web app process.
3. **Multi-tenant cloud** — adds vLLM-class LLM serving, horizontally scaled API and worker
   replicas, hosted object storage, hosted vector index, and a managed Postgres.

The pluggability (`NFR-11`) that makes this work is established in the lower-tier specs:
`LLM_PROVIDER`, `OBJECT_STORE_URL`, `*_SERVICE_URL`, `VECTOR_INDEX_URL` (see
`.env.example` and `architecture_overview.md` §4). This directory defines the **runtime topology
contracts** above those config variables.

## Read in this order

| Spec | Defines | Why |
|---|---|---|
| `reasoning_llm_serving.md` | how the agent's reasoning LLM (Ollama default, vLLM/hosted-API opt-ins) is served, scaled, and selected per role | the agent's "brain" sits behind the `LLMProvider` interface; this is where the brain actually runs |
| `domain_model_serving.md` | how the biological foundation models (Boltz-2, ESMFold, AlphaGenome, Evo 2, RFdiffusion, LigandMPNN, …) are served and scheduled | the heaviest compute; GPU workers + job queue |
| `agent_runtime_serving.md` | how FastAPI, the policy kernel, and harness executors run (replicas, concurrency, checkpoints, sequencing, graceful shutdown) | the runtime that ties adapters and typed skills together |
| `frontend_deployment.md` | how the Next.js web app is built/served now and how the macOS native shell ports onto the same wire contract | the user-facing surface and its portability story |

## Shared conventions

- **The contracts are invariant; the runtimes are interchangeable.** Switching the reasoning
  LLM from Ollama (local) to vLLM (cluster) to OpenAI (hosted) is `LLM_PROVIDER=…` and
  optional URL/key — not a code change. Same rule for object store, vector index, and the
  service URLs.
- **Local-first is a first-class regime, not a demo path.** Any feature that does not work
  with `LLM_PROVIDER=ollama` + `OBJECT_STORE_URL=file://…` + a single API process must be
  explicitly documented as cluster-only and gated behind a config check.
- **Heavy work is async, everywhere.** Synchronous request paths terminate quickly; long jobs
  (structure prediction, large model inference, genome-scale scans) dispatch via the Redis job
  layer and stream liveness back through SSE (`streaming_protocol.md` §5). This applies in all
  three deployment regimes — the queue is local in regime 1, distributed in regime 3.
- **Provenance is the source of truth across replicas.** State and evidence persist to
  Postgres + object store + audit log; nothing of consequence lives only in process memory
  (`specs/data/provenance_model.md`). Replicas are stateless w.r.t. run identity; sequencing
  within a single SSE stream is sticky (`agent_runtime_serving.md` §4).
- **Privacy is a deployment property, not just a code property.** Switching to a hosted LLM or
  cloud object store is an explicit, audit-logged configuration choice and surfaces in the UI
  before private content is sent off-host (`llm_service.md` §8, `chat_interface.md` §11).
- **Reproducibility crosses regimes.** A run executed on a workstation must be reproducible on
  a cluster from its persisted provenance (`PROV-6`); tool/model versions are the contract,
  not the process they ran in.

## Deployment regime matrix

| Concern | Regime 1: single-user local | Regime 2: workstation / lab | Regime 3: multi-tenant cloud |
|---|---|---|---|
| API + agent runtime | 1 uvicorn/local executor | 1–2 API + executor replicas | N API/executor replicas, independently autoscaled |
| Reasoning LLM | Ollama (`gemma4:4b`) on host | Ollama on host or shared GPU | **vLLM / SGLang / TGI** (or hosted API) |
| Domain models (Boltz/ESMFold/…) | CPU fallback (slow) or one GPU job | Dedicated GPU worker(s), Redis queue | GPU worker pool, autoscaled per queue |
| Postgres | local container | local container or lab DB | managed Postgres |
| Redis | local container | local container | managed Redis / Elasticache |
| Object store | `file://` local FS | local MinIO or NAS | hosted S3-compatible |
| Vector index | local (FAISS / sqlite-vec / Qdrant single) | local Qdrant / Weaviate | hosted Qdrant / pgvector / managed |
| Frontend | `npm run dev` or single Next.js server | shared Next.js server | CDN-fronted Next.js (Vercel/edge) |
| Auth | loopback session | loopback or simple SSO | full identity / SSO / RBAC |
| Telemetry | local logs | local logs + LangSmith opt-in | central tracing/metrics |

## Where this directory sits in the architecture

The serving specs read *across* the other spec families:

- They consume the **service contracts** (`specs/services/*`) and decide which services live
  in-process vs as standalone workers (`ADR-0003`).
- They consume the **agent contract** (`specs/agent/skill_plugin_contract.md`,
  `state_schema.md`, `control-flow/*`) and decide how many harness executors run, how checkpoints
  work, and how pauses survive restarts.
- They consume the **data contracts** (`specs/data/*`) and pick backends (`file://` vs S3,
  local vector store vs hosted).
- They feed the **interface contracts** (`specs/interface/*`) by guaranteeing the SSE/REST
  wire is stable across replicas and reconnects.

## Stack pointers

Implementation directories: `infra/compose/`, `infra/k8s/`, `infra/terraform/`, `infra/docker/`,
`scripts/dev_*.sh`. Env contract: `.env.example`. Diagram:
`documentation/diagrams/deployment_topology.mmd` (to be added).

## Related

`documentation/explanation/architecture_overview.md` §6–§8 ·
`specs/services/README.md` · `specs/data/README.md` · `specs/interface/README.md` ·
`specs/agent/control-flow/README.md`.
