# Reasoning-LLM Serving

> Status: Draft v0.1. How the agent's **reasoning LLM** — the brain behind intent classification,
> risk classification, entity resolution, planning, critique, and report writing — is actually
> served. The provider-agnostic interface is `specs/services/llm_service.md`; the consumers are
> `specs/agent/nodes/*` and `specs/agent/control-flow/*`. This spec defines runtimes, deployment
> regimes, throughput/latency expectations, multi-tenancy, and the **vLLM-vs-Ollama decision**.

## 1. Scope

The reasoning LLM is distinct from the **domain foundation models** (AlphaGenome, Evo 2,
ESMFold, Boltz-2, RFdiffusion, …) which are served separately
(`domain_model_serving.md`). The reasoning LLM is text-in/text-out (with structured-output
modes) and is invoked by **every LLM-backed node** on every run. Its throughput, latency, and
privacy posture therefore set the agent's overall responsiveness and trust ceiling.

## 2. Runtimes (and when to use which)

| Runtime | Best fit | Strengths | Weaknesses |
|---|---|---|---|
| **Ollama** (default) | single-user local / workstation | trivial to install, single-binary, no-key, native streaming + tool calls, model pull is one command, fully on-host (`NFR-7`) | one request at a time per model instance (effectively serial), no PagedAttention, GPU memory underused under concurrent load |
| **vLLM** | lab cluster, multi-user, larger models | **PagedAttention** + continuous batching → high throughput; tensor parallel across GPUs; OpenAI-compatible HTTP API; mature | heavier ops (Python+CUDA build, GPU required for the useful regime); overkill for a single user on a laptop |
| **SGLang / TGI** | same niche as vLLM | competitive throughput; SGLang strong on structured generation | same ops weight; pick one; default to vLLM unless a specific reason |
| **Hosted API** (OpenAI / Anthropic / OpenAI-compatible) | when capability ceiling matters more than locality | best-in-class models, zero ops, generous context | data leaves host (consent gate, `llm_service.md` §8); per-token cost; provider drift hurts reproducibility |
| **llama.cpp / mlx / candle** (advanced) | Apple Silicon / experimental | Apple-native (MLX), tiny footprint | not a default; users who want this can run it through Ollama, which embeds llama.cpp |

### 2.1 The vLLM-vs-Ollama decision (direct answer)

**For the default local-first product, vLLM is overkill.** The reasoning-LLM workload at single-user
scale is one LLM call at a time per node (planner, critic, report writer) with bursts during
planning. Ollama's "one request at a time" model is *fine* for that — the user is one human and
the agent serializes its own steps anyway. Adding vLLM in regime 1 means: Python/CUDA build chain,
GPU residency, a separate process to manage, and operational complexity that buys nothing.

**vLLM becomes correct when at least one of these is true:**

- Many concurrent users / tenants share one LLM (cluster or hosted CellXP) — continuous batching
  is where vLLM dominates.
- The chosen model is large enough to need **tensor parallelism across multiple GPUs** (≥ 70B,
  or 30B with 4-bit on a tight VRAM budget) — Ollama is single-process.
- The agent runs many parallel subagents per turn (a deepagents-style spawn fan-out) and the
  reasoning LLM is the bottleneck — batched throughput matters.
- A team standardizes on an **OpenAI-compatible local endpoint** behind a router so different
  apps share one serving plane.

In all other cases, **Ollama is the right default**. The right architecture is therefore: keep
Ollama as the default backend, treat vLLM as a first-class opt-in `LLM_PROVIDER`, expose both
via the existing `LLMProvider` interface, and never let the choice leak into business logic
(`llm_service.md` §5).

## 3. Default: Ollama (regime 1)

### 3.1 Topology

```
                ┌──────────────────────────────────┐
                │   FastAPI + LangGraph (1 proc)   │
                │   LLMProvider("ollama")          │
                └──────────────┬───────────────────┘
                               │ httpx (HTTP, native streaming)
                               ▼
                ┌──────────────────────────────────┐
                │  ollama server (localhost:11434) │
                │  gemma4:4b  (default model)      │
                └──────────────────────────────────┘
```

- **Process model.** One `ollama serve` daemon (host process or `infra/compose/ollama` service).
- **GPU.** Optional. On Apple Silicon, Metal is automatic; on NVIDIA, CUDA is auto-detected;
  CPU fallback works for the default small model (`gemma4:4b`).
- **Concurrency.** Effectively serial per model. Acceptable because the agent serializes its
  reasoning steps within a single run; multi-run concurrency in regime 1 is single-user (rare).
- **Model loading.** Ollama keeps the last-used model resident; switching costs an unload+load.
  Run-time per-role model overrides are allowed but should be used sparingly in regime 1 to
  avoid model thrash (§5).

### 3.2 Configuration

```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma4:4b
LLM_REQUEST_TIMEOUT_S=120
LLM_MAX_TOKENS=2048
LLM_TEMPERATURE_DEFAULT=0.2
# concurrency knobs (set on the ollama daemon process, surfaced to the agent via §3.4)
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=1
```

### 3.3 Reliability

- **Timeouts + retries** with capped backoff in the LLM service; failures become recoverable
  `RunError`s the agent can route around (`NFR-6`).
- **Health check.** Startup probes `GET /api/tags`; the API refuses to dispatch LLM-backed nodes
  if the daemon is unreachable, with a clear user-facing error (no silent fallback to a remote
  provider).
- **Model availability.** `ollama pull <model>` is an operational prerequisite documented in
  setup; the LLM service refuses with an actionable error if a requested model is missing.

### 3.4 Concurrency under sub-agent fan-out

CellXP is a hierarchical multi-agent system (`multi_agent_architecture.md`,
`.agents/guidelines/deepagents.md`): a supervisor can spawn L2 capability agents that can spawn
L3 isolated sub-agents, and several of those may call the reasoning LLM in parallel within a
single user turn (e.g. a planner spawning concurrent investigators, a critic running alongside
a report writer). Ollama serializes requests per loaded model by default; without tuning, that
fan-out becomes wall-clock additive.

The mitigations are knobs on both sides — the daemon and the agent layer — and they MUST be
configured together:

- **Daemon side.** `OLLAMA_NUM_PARALLEL` (env on the `ollama serve` process) lets one loaded
  model serve N concurrent requests by splitting the KV cache. Throughput is sub-linear in N
  (one GPU is one GPU), but latency stops adding up across fan-out. A practical default on a
  consumer GPU with the default small model is `OLLAMA_NUM_PARALLEL=4`; on a single-tenant
  workstation with a larger GPU, scale up until VRAM (KV cache ≈ `num_parallel × context_length
  × model_state`) is the binding constraint. `OLLAMA_MAX_LOADED_MODELS` controls how many
  distinct models can be resident — relevant only if you opt into per-role overrides (§5).
- **Pin one model per regime-1 deployment.** Cross-model swaps cost seconds of unload/load —
  worse than the serialization they would replace. In regime 1, the LLM service SHOULD default
  per-role overrides off and let all sub-agents share `LLM_MODEL`. Override only when the
  capability gap is large enough to be worth the swap cost (rare for orchestration roles).
- **Agent side.** The `LLMProvider` advertises a `max_concurrent` capability
  (`llm_service.md` §3) sourced from `OLLAMA_NUM_PARALLEL` (or the provider equivalent). The
  supervisor's spawn policy MUST treat this as a budget: when more LLM-calling sub-agents are
  requested than slots are available, they queue rather than stampede. The supervisor SHOULD
  prefer **fan-out of domain-model work** (Boltz/ESMFold/AlphaGenome via the worker pool,
  which is independently scaled in `domain_model_serving.md`) over **fan-out of LLM-calling
  sub-agents**, since the former is what GPU workers are for.
- **When to leave Ollama.** If a deployment routinely needs more LLM-calling sub-agents in
  flight than the host's VRAM affords parallel slots, or per-role model heterogeneity becomes
  load-bearing, Ollama is the wrong runtime — switch `LLM_PROVIDER` to `openai_compatible`
  with vLLM/SGLang/TGI behind it. Continuous batching is exactly the workload vLLM exists for
  (§4). The agent contract does not change.

In short: for typical CellXP usage (one user, one turn at a time, supervisor mostly
sequential with bounded fan-out), Ollama with `OLLAMA_NUM_PARALLEL=4` and a single pinned
model is fine. The signal to graduate is sustained sub-agent fan-out beyond the slot budget,
or per-role model heterogeneity that forces model-swap thrash.

## 4. Cluster: vLLM (regime 3)

### 4.1 Topology

```
                ┌────────────────────────────────────────┐
                │   FastAPI + LangGraph (N replicas)      │
                │   LLMProvider("openai_compatible")      │
                │   base_url = LLM_BASE_URL (internal LB) │
                └──────────────┬──────────────────────────┘
                               │ HTTP/2, streaming
                               ▼
                ┌────────────────────────────────────────┐
                │   vLLM serving cluster (M replicas)     │
                │   OpenAI-compatible HTTP/SSE endpoint   │
                │   tensor-parallel, continuous batching   │
                │   models: gemma-2-27b-it / llama-…-70b   │
                └────────────────────────────────────────┘
```

- **vLLM speaks an OpenAI-compatible API.** CellXP uses `LLM_PROVIDER=openai_compatible` with
  `OPENAI_BASE_URL=https://llm.internal/v1` (no API key, or a shared cluster key). The same
  `LLMProvider` code paths work whether the endpoint is OpenAI, Anthropic via gateway, vLLM,
  SGLang, or TGI.
- **Multi-replica.** Front vLLM with the cluster's standard L7 LB; cap per-replica concurrency
  via vLLM's `--max-num-seqs`.
- **Tensor parallel.** Set `--tensor-parallel-size` to the number of GPUs per replica when the
  model needs it (e.g. 70B at fp16).
- **Quantization.** AWQ/GPTQ/INT8 supported by vLLM; pick per VRAM budget. Document the chosen
  quantization in deployment notes; it is part of provenance via `tool_version`.
- **Model registry.** vLLM serves one base model per replica (model swap is restart-only).
  Mixing models across replicas requires a router (e.g. LiteLLM) that maps logical model names
  to backend URLs.

### 4.2 Configuration

```
LLM_PROVIDER=openai_compatible
OPENAI_BASE_URL=https://llm.internal/v1
OPENAI_API_KEY=...                # cluster-internal token
LLM_MODEL=gemma-2-27b-it
LLM_REQUEST_TIMEOUT_S=300
LLM_MAX_TOKENS=4096
```

### 4.3 Throughput & latency

- vLLM's **continuous batching** dramatically increases tokens/sec under concurrency. Plan
  capacity per concurrent-active-run × tokens-per-run, not per request.
- **TTFB (time-to-first-token)** is the user-visible metric for streaming surfaces
  (`streaming_protocol.md`). Target < 1 s p95 for the planner; the report writer is allowed
  longer.
- **p99 latency tail** is dominated by batch-prefill on long prompts. Cap input context per
  role (§5) and prefer summarization in the harness over raw concatenation
  (`harness_and_context_engineering.md`).

## 5. Per-role model overrides

The LLM service supports `LLM_MODEL_<ROLE>` overrides (`llm_service.md` §5) so different nodes
can use different models without code changes. Default policy:

| Role | Default | Notes |
|---|---|---|
| `intent_classifier` | small fast model | tens of tokens output; latency-bound |
| `risk_classifier` | small fast model | same |
| `entity_resolver` | small + tool-calling | structured output |
| `planner` | medium model | longer context; benefits from a stronger model |
| `critic` | medium model | structured critique; benefits from determinism |
| `report_writer` | medium-to-large model | quality-bound; can run slower |

In regime 1 the practical default is "one model for everything" (`gemma4:4b`) to avoid Ollama
model-swap thrash (§3.4). In regime 3 with vLLM/hosted, per-role overrides are cheap and
recommended. Per-role model identity + version is recorded in `Provenance.tool_version` for
every call (`PROV-1`).

## 6. Structured outputs & tool calling

- The LLM service validates JSON-mode / tool-call outputs against the caller's Pydantic schema
  and surfaces parse failures as recoverable errors (`llm_service.md` §3).
- vLLM/SGLang support **constrained decoding** (JSON schema, regex). Ollama supports JSON mode
  but constrained decoding varies by model. The LLM service MUST treat structured-output
  guarantees as best-effort and ALWAYS revalidate.
- Tool-call schemas are owned by the calling node, not the provider.

## 7. Embeddings

Embeddings for RAG are NOT served from the reasoning LLM by default. They live in a dedicated
embedding provider (`specs/services/rag_service.md` open question §10.2), typically a small
local model (e.g. `nomic-embed-text` via Ollama in regime 1, a vLLM embedding server or hosted
endpoint in regime 3). The choice is a separate configuration axis (`EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`) so an upgrade does not require re-embedding the whole vector index unless
intentional.

## 8. Multi-tenancy & privacy

- Regime 1 is single-user; tenant isolation is OS-level. The LLM server is loopback-bound.
- Regime 3 routes all tenants through the same vLLM cluster by default; per-tenant isolation is
  achieved via the API layer (each request carries an authenticated session; the LLM service
  never sees cross-tenant data because each call is scoped to a single run). For stricter
  tenants (e.g. hospital/IRB-flagged sessions, `FC-1`), the deployment MAY route to a
  dedicated vLLM pool via `LLM_BASE_URL` per session class; this is a deployment configuration,
  not a code path.
- Switching to a hosted provider is an explicit, audit-logged action (`llm_service.md` §8) and
  surfaces in the chat UI before private content is sent off-host
  (`chat_interface.md` §11).

## 9. Observability

- Per-call metrics: model, role, prompt tokens, completion tokens, TTFB, total latency, cache
  hit/miss, parse-failure count, retry count.
- Tracing: every LLM call is a `Step` in the run trace (`PROV-1`); the LLM service also emits
  structured logs with `request_id` and `run_id`. LangSmith integration is opt-in
  (`.agents/guidelines/langsmith.md`).
- Errors NEVER include prompts/secrets in user-facing surfaces (`API-10`); prompt persistence
  is governed by run-retention policy (`specs/data/*`).

## 10. Failure modes & fallbacks

- **Provider unreachable.** Fail the in-flight LLM call with a recoverable `RunError`. Optional
  configured secondary provider (`LLM_FALLBACK_PROVIDER`) MAY be tried; otherwise emit a
  user-facing error and let the agent route around (`NFR-6`). No silent fallback to a remote
  provider when local is configured (privacy invariant).
- **Token budget exhausted.** Truncate via the harness summarization step, not by silent
  context drop (`harness_and_context_engineering.md`).
- **Structured-output parse failure.** One retry with a stricter prompt, then escalate to the
  caller as a recoverable error.
- **Model swap thrash (regime 1).** If per-role overrides cause repeated Ollama unload/load,
  the service auto-collapses to a single role-default per run and warns in run telemetry
  (§3.4).
- **Sub-agent slot exhaustion (regime 1).** When LLM-calling sub-agents are requested beyond
  the provider's advertised `max_concurrent`, the supervisor MUST queue rather than dispatch in
  parallel; queued calls surface as `activity.update` ("waiting for LLM slot") rather than
  silently extending tail latency (§3.4).

## 11. Migration paths

- Regime 1 → 2: Move Ollama to a workstation GPU; bump `LLM_MODEL` to a larger model (still
  Ollama). No code changes.
- Regime 2 → 3: Stand up vLLM behind an internal LB, switch `LLM_PROVIDER=openai_compatible`
  with `OPENAI_BASE_URL=https://llm.internal/v1`, optionally enable per-role overrides. No
  code changes; provenance gains the new `tool_version` strings.
- Regime 3 (vLLM) → hosted: switch `LLM_PROVIDER=openai|anthropic`, set API key + base URL,
  surface the consent gate in the UI. No code changes.

## 12. Requirements

- **RLS-1** The reasoning-LLM serving MUST be selectable via `LLM_PROVIDER` with no business
  logic hard-coding a vendor or endpoint (`llm_service.md` §5).
- **RLS-2** Regime 1 (Ollama on localhost) MUST work for every LLM-backed node with no
  external network access; failing to reach a configured local provider MUST NOT silently fall
  back to a remote provider.
- **RLS-3** vLLM/openai-compatible deployments MUST advertise the same `LLMProvider`
  capabilities as Ollama (streaming, JSON/tool-calls, embeddings opt-in).
- **RLS-4** Per-role model overrides MUST be configuration-only and MUST be recorded in
  `Provenance.tool_version` per call.
- **RLS-5** Switching to a hosted provider MUST be audit-logged and surfaced in the UI before
  the first private payload is sent off-host.
- **RLS-6** Throughput-critical deployments (regime 3) MUST use a runtime with continuous
  batching (vLLM/SGLang/TGI) or a hosted provider; Ollama is NOT a supported regime-3 backend.
- **RLS-7** Embedding model selection is independent of the reasoning-LLM provider and MUST
  not be coupled in code paths.
- **RLS-8** All LLM calls MUST emit a `Step` with model, version, params, prompt-token,
  completion-token, and latency, regardless of provider.
- **RLS-9** The `LLMProvider` MUST advertise a `max_concurrent` capability sourced from the
  underlying runtime (e.g. `OLLAMA_NUM_PARALLEL`), and the supervisor's sub-agent spawn policy
  MUST treat it as a budget (queue beyond the budget, do not stampede) (§3.4,
  `llm_service.md` §3).

## 13. Open questions

- Default per-role overrides in regime 3 (which roles get the bigger model out of the box).
- Whether to ship a built-in LiteLLM router as a sub-component for teams who want one URL,
  many backends.
- Streaming reasoning channel: when the provider does not support partial-tokens-with-tool-calls
  cleanly (some vLLM versions), what is the user-visible degradation?
- Quantization defaults for regime 3 (AWQ vs GPTQ vs INT8) — likely a deployment, not spec,
  decision.

## 14. Related

`specs/services/llm_service.md` · `specs/serving/domain_model_serving.md` ·
`specs/serving/agent_runtime_serving.md` · `specs/agent/nodes/*` ·
`specs/agent/harness_and_context_engineering.md` · `.env.example` ·
`docker-compose.yml` · `documentation/explanation/architecture_overview.md` §2.
