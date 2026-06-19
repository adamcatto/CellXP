# Agent Runtime Serving

> Status: Draft v0.1. How the **FastAPI + LangGraph agent runtime** is deployed, replicated,
> and kept correct across restarts, replicas, and reconnects. The agent's design is in
> `specs/agent/*`; this spec defines the **process and replication topology** that lets it run
> in regimes 1–3 (`README.md`) without changing the agent contract. Distinct from
> `reasoning_llm_serving.md` (LLM) and `domain_model_serving.md` (oracles).

## 1. Scope

The agent runtime is the FastAPI process that:

- hosts the REST + SSE endpoints (`specs/interface/api_contracts.md`),
- compiles and executes the LangGraph supervisor + subgraphs (`specs/agent/graph_spec.md`,
  `state_schema.md`),
- writes/reads run state through the persistence layer (`specs/data/*`),
- dispatches heavy work to the job layer (`control-flow/concurrency.md`,
  `domain_model_serving.md`).

This spec defines: process model, replication, sticky SSE sequencing, checkpointing &
resumption, graceful shutdown, capacity limits, and observability.

## 2. Process model

```
┌────────────────────────────────────────────────────────────────────┐
│  uvicorn (asgi) / process                                           │
│  ├─ FastAPI app                                                     │
│  │   ├─ routers (sessions / runs / artifacts / reviews / uploads)   │
│  │   ├─ SSE handler (per-run, ordered, replayable)                  │
│  │   └─ middleware (auth, request id, idempotency, problem+json)    │
│  ├─ LangGraph compiled graph                                        │
│  │   ├─ supervisor + subgraphs                                       │
│  │   └─ checkpointer (Postgres for durable; Redis for ephemeral)     │
│  ├─ Service registry (in-process services)                          │
│  ├─ Job client (Redis Streams producer)                             │
│  └─ Background tasks (heartbeats, cache pruning, audit flush)       │
└────────────────────────────────────────────────────────────────────┘
```

- **Single process per replica.** No multi-process fork inside one container (uvicorn
  `--workers 1`). Horizontal scaling is done at the container/pod level, not by process
  forking — the LangGraph in-memory caches and the SSE registry assume a single process.
- **Asyncio everywhere.** All I/O is async; service calls that are intrinsically synchronous
  (CPU heavy) run via `asyncio.to_thread` or are dispatched as jobs. Blocking the event loop
  for > 100 ms is a bug.
- **Workers are separate processes** (see `domain_model_serving.md` §5); the agent runtime
  process does not host worker logic.

## 3. Replication

| Regime | Replicas | Notes |
|---|---|---|
| 1 (single-user local) | 1 | run via `scripts/dev_api.sh` or `infra/compose/docker-compose.yml` |
| 2 (workstation / lab) | 1–2 behind reverse proxy | second replica for restart-without-downtime |
| 3 (multi-tenant cloud) | N, HPA on request-latency / CPU | k8s `Deployment`; ingress with sticky SSE (§4) |

Replicas are **stateless** with respect to **durable** run identity: run state, checkpoints,
artifacts, evidence, and audit live in Postgres + object store + Redis. Any replica can take a
request for any run (with the §4 caveat for in-flight SSE streams).

**No shared file system.** Anything that needs to be shared lives in Postgres, Redis, or the
object store — not in process-local files. The deepagents virtual filesystem
(`session_types.md` §2 `files`) is backed by the persistence layer, not the host FS.

## 4. SSE sequencing & sticky sessions

A single SSE stream MUST be served by a single replica for the lifetime of that connection
(events are sequenced in memory on that replica). The system is sticky at the **SSE connection**
boundary, not the **run** boundary:

- POST to `/runs` (start a run) may land on any replica; that replica becomes the run's
  **executor** until the graph yields (await job, await user, complete).
- GET `/runs/{id}/events` (SSE) lands on **the executor replica** for that run while it is
  executing. If routed to a different replica:
  - Executing run on a different replica → ingress sticks via `run_id` hash, OR the receiving
    replica proxies the stream from the executor, OR the receiving replica refuses with a
    redirect to the canonical stream URL. We pick **ingress hash on `run_id`** for v1.
  - Run is paused (`awaiting_*`) or completed → any replica can serve from the checkpointed
    state + replayable durable events (`api_contracts.md` §8). The reader gets the snapshot
    plus a tail.

Reconnect/replay uses `Last-Event-ID` and the durable event log; ephemeral events
(`reasoning.*`, `activity.update`) MAY be dropped on replay
(`streaming_protocol.md` §9).

## 5. Checkpointing & resumption

LangGraph's checkpointer is configured to persist to **Postgres** for the run's durable state
(messages, plan, subtasks, steps, evidence, artifact refs, errors, status) and to **Redis** for
short-lived ephemeral state (per-step counters, in-flight reasoning buffers). On replica
restart or run hand-off:

- a different replica MUST be able to **resume an awaiting-input/awaiting-review run** from
  Postgres state with no data loss; pending clarification / review cards re-stream
  (`streaming_protocol.md` §9, `control-flow/pause_and_resume.md`),
- in-flight (running) graph execution that was interrupted by an executor crash is **resumed
  from the last checkpoint**, not restarted from scratch; idempotent steps de-dupe via
  `input_hash`,
- non-idempotent steps must declare themselves as such; the resumer's policy is "re-run only if
  the step's `Provenance.idempotent=true`" — others surface as `error.added` requiring user
  input or are skipped per the run's policy (`control-flow/replanning_and_budget.md`).

Checkpoint cadence is per-node-completion by default; long nodes opt into intra-node
checkpointing where it matters (e.g. the planner persisting subtasks one-by-one as it builds
the plan).

## 6. Concurrency model

Per replica:

- `AGENT_MAX_CONCURRENT_RUNS` (default tuned per regime; 4 in regime 1, e.g. 32 in regime 3):
  the maximum number of runs an executor replica will keep in active graph execution
  simultaneously. Excess `POST /runs` returns `429` (`api_contracts.md` §2) with a clear
  back-off; the client retries against the load balancer.
- `AGENT_MAX_LLM_CONCURRENT` (per role, per replica): bounded by the reasoning-LLM backend's
  concurrency (Ollama serial, vLLM batched). The LLM service enforces.
- `AGENT_MAX_JOBS_QUEUED` (per run): cap on in-flight heavy jobs per run; prevents one run
  flooding the worker pool. Excess jobs queue locally with `activity.update` reporting.

Per cluster (regime 3):

- HPA on **request-latency p95** plus **CPU**; scale on actual saturation, not on request
  rate alone (most agent requests are I/O-bound).
- Per-tenant quotas at the API layer prevent one tenant starving others.

## 7. Graceful shutdown

On SIGTERM:

1. The replica stops accepting new connections (`/healthz` flips to "draining").
2. It finishes the current node executions and **checkpoints** the run state.
3. In-flight SSE streams receive a `stream.reset` event with the snapshot URL and next
   sequence (`api_contracts.md` §8); the client reconnects to a different replica and
   resumes.
4. Background tasks (audit flush, cache pruning) complete to a quiescent point.
5. The process exits within `SHUTDOWN_GRACE_S` (default 30 s) or is force-killed by the
   orchestrator.

A crashed (non-graceful) replica is handled by the resumption flow (§5): another replica picks
up the run from its last checkpoint.

## 8. Health & readiness

- `/healthz` — liveness; cheap, no DB; flips to "draining" during shutdown.
- `/readyz` — readiness; checks Postgres reachable, Redis reachable, default LLM provider
  responsive, object store reachable. A non-ready replica is removed from the LB.
- `/api/v1/diagnostics` (auth-gated) — model registry, service registry, queue depths,
  checkpoint backlog (for operators; not user-facing).

## 9. Capacity & budgeting

- Per-run **budgets** (`state_schema.md` §15) cap tokens, jobs, time, and dollars (when a paid
  provider is configured). Exceeded budgets trigger the budget-replan node
  (`control-flow/replanning_and_budget.md`).
- Per-tenant **capacity** (regime 3) is enforced at the API layer; over-quota returns `429`
  with a clear `Retry-After`.
- The replica reports its own observable saturation in `/readyz` for the autoscaler.

## 10. Observability

- **Structured logs** with `request_id`, `run_id`, `session_id`, `tenant_id`, latency, status.
- **Tracing**: every API request and every node execution is a span; LangSmith integration is
  opt-in (`.agents/guidelines/langsmith.md`).
- **Metrics**: request RPS/latency, run-start RPS, runs-in-progress, run completion status mix,
  per-node latency, LLM tokens, job-queue depths.
- **Audit log** (`specs/data/audit_log.md`) writes are non-blocking (queued) but durable before
  the user receives the corresponding response.
- Logs MUST NOT contain secrets, raw prompts, or raw biological payloads (`API-10`).

## 11. Local development

- `scripts/dev_api.sh` runs uvicorn against the local Postgres/Redis/Ollama stack
  (`docker-compose.yml`).
- Hot reload during development (`uvicorn --reload`) is dev-only and disables the in-memory
  service registry's warm caches; production deployments NEVER use `--reload`.
- `tests/` covers the agent runtime with a real Postgres + Redis via testcontainers; LLM and
  domain models are mocked unless explicitly enabled.

## 12. Authentication & authorization

- Regime 1: loopback-bound, OS-level single-user.
- Regime 2: optional simple SSO; sessions belong to authenticated users.
- Regime 3: full identity / SSO / RBAC; every request authorized per-session, per-run, per-artifact
  (`API-3`).

The runtime layer enforces auth at the FastAPI middleware level; services and the graph never
see unauthenticated requests.

## 13. Failure modes

- **Postgres unreachable.** New run creation fails fast (5xx + clear error). Active SSE
  streams continue serving from in-memory state until they need to checkpoint, then surface a
  recoverable error.
- **Redis unreachable.** Ephemeral checkpoint + job dispatch fail; the run fails gracefully
  with partial results if any (`NFR-6`); reconnect/replay disabled until Redis is back.
- **Object store unreachable.** New artifacts cannot be persisted; the run halts heavy artifact
  emission with a recoverable error; small inline artifacts continue.
- **LLM provider unreachable.** See `reasoning_llm_serving.md` §10.
- **Worker pool saturated.** Job queue depth grows; runs see longer `activity.update`
  reporting; the autoscaler responds in regime 3.
- **Cascading failure / overload.** Replica admits less aggressively (lower
  `AGENT_MAX_CONCURRENT_RUNS`) and increases retry/backoff; the LB sheds load via `429`.

## 14. Migration paths

- Regime 1 → 2: Move the API replica behind a reverse proxy; optionally run a second replica
  for restart-without-downtime; configure shared Postgres/Redis/object-store endpoints.
- Regime 2 → 3: Add ingress with sticky-by-`run_id` hashing; configure HPA; tighten per-tenant
  capacity caps; enable distributed tracing; promote Postgres/Redis to managed offerings.
- All migrations are config-only with respect to the agent contract (`NFR-11`).

## 15. Requirements

- **ARS-1** Replicas MUST be stateless with respect to durable run identity; all consequential
  state MUST live in Postgres / Redis / object store, not process memory.
- **ARS-2** SSE streams MUST be sticky-by-`run_id` while a run is executing; replicas not
  executing the run MUST be able to serve replay/snapshot reads.
- **ARS-3** LangGraph checkpoints MUST persist enough state to resume an awaiting-input /
  awaiting-review run from a different replica with no user-visible data loss.
- **ARS-4** SIGTERM MUST drain in-flight runs into checkpoints within `SHUTDOWN_GRACE_S` and
  emit `stream.reset` to active SSE consumers.
- **ARS-5** `/healthz` MUST be cheap and MUST flip during drain; `/readyz` MUST gate the
  replica out of the LB on dependency failure.
- **ARS-6** Per-run, per-replica, and per-tenant concurrency limits MUST be enforced; over-limit
  requests MUST receive `429` with `Retry-After`.
- **ARS-7** Logs and traces MUST NOT contain secrets, raw prompts, or raw biological payloads
  (`API-10`).
- **ARS-8** Authentication and authorization MUST happen at the runtime boundary; services and
  the graph MUST NEVER receive an unauthenticated request.
- **ARS-9** Non-idempotent steps MUST declare themselves; the resumer's default policy is
  re-run-if-idempotent, surface-otherwise.
- **ARS-10** The runtime MUST be deployable in regimes 1–3 with config-only changes; the agent
  graph MUST NOT have regime-conditional branches.

## 16. Open questions

- Sticky-SSE policy: ingress hash vs. executor-replica proxy. Hash is simpler; proxy is more
  flexible. Default to hash; revisit if multi-region demands.
- Whether to ship a **per-tenant queue** at the runtime layer (rate-limiting) or push it down
  to ingress.
- LangGraph checkpoint compaction strategy (delta vs. snapshot frequency) — primarily a perf
  question.
- Multi-region: does CellXP ever go multi-region in v1? If yes, run affinity to one region for
  the run lifetime; SSE cannot cross regions cleanly.

## 17. Related

`specs/agent/state_schema.md` · `specs/agent/graph_spec.md` ·
`specs/agent/control-flow/{run_lifecycle,concurrency,pause_and_resume,replanning_and_budget}.md` ·
`specs/interface/api_contracts.md` · `specs/interface/streaming_protocol.md` ·
`specs/serving/domain_model_serving.md` · `specs/serving/reasoning_llm_serving.md` ·
`specs/data/{relational_schema,object_storage,audit_log}.md` ·
`documentation/explanation/architecture_overview.md` §5–§8 · `.env.example`.
