# ADR-0003 — Keep service boundaries logical (in-process by default)

- **Status:** Accepted (v0.1)
- **Date:** initial backend layout
- **Related:** `documentation/explanation/architecture_overview.md` §4,
  `specs/services/README.md`, `specs/serving/domain_model_serving.md`,
  `specs/serving/agent_runtime_serving.md`

## Context

CellXP has nine domain services (variant effect, GWAS, CRISPR, structure, binding,
annotation/reference, RAG, visualization, origami) plus the LLM service. Each wraps a
coherent capability with its own dependencies, model invocations, and external integrations.

Two extremes were on the table:

1. **Microservices from day one.** Each service is its own HTTP-served container with its
   own deployment, schema, version, and on-call. Strong isolation; very high operational tax;
   distributed-systems failure modes (timeouts, retries, partial failures, version skew)
   from day one in a local-first single-user product.
2. **Monolith with no boundaries.** All capability code lives in one module without a stable
   interface. Cheap to start; expensive to evolve; impossible to scale a single capability
   independently when one becomes the bottleneck.

CellXP needs:

- **Local-first simplicity** — a single workstation must run the whole stack (`NFR-7`).
- **Pluggability** of individual capabilities (swap a model, host a service remotely) without
  changing the agent (`NFR-11`).
- **Independent scaling** of heavy capabilities (Boltz/ESMFold worker pools) without forcing
  every capability into the same operational shape.
- A stable contract the agent can program against, regardless of where the capability runs.

## Decision

Make service boundaries **logical**, not deployment-defined. Each service is:

- A Python class under `src/backend/cellxp/services/<name>/` with a uniform `Service` base and
  registry entry (`services/base.py`, `services/registry.py`).
- A typed operations interface (`ServiceResult[T]` over Pydantic models) defined by
  `specs/services/<name>.md`.
- **Callable in-process by default.** The agent imports the registry and dispatches operations
  as method calls.
- **Promotable to an out-of-process HTTP microservice** behind the same Python interface, with
  no agent-side code change. A remote service is configured via env (`*_SERVICE_URL` in
  `.env.example`) and accessed through a thin HTTP client that implements the same `Service`
  Protocol.

Heavy work (GPU model inference, long pipelines) is **always** dispatched through the **job
layer** (Redis queue + workers), independent of whether the service itself is in-process or
remote (`specs/serving/domain_model_serving.md`). Job dispatch is orthogonal to deployment
boundary.

Concretely:

- In regime 1 (single-user local), all services run in-process; the LLM service speaks to
  local Ollama; domain-model jobs queue to a local worker.
- In regime 2 (workstation/lab), heavy services may be promoted to standalone HTTP services
  on dedicated GPU hosts via the env config; the agent contract is unchanged.
- In regime 3 (multi-tenant cloud), services run as independent k8s workloads with their own
  autoscaling; the agent contract is still unchanged.

## Consequences

**Positive**

- Local-first works out of the box: one process, no Kubernetes, no service mesh, no
  network failures to debug.
- Production scaling does not require a rewrite — each service can be promoted independently
  when its load justifies the operational tax.
- The agent contract is stable: nodes call `services.crispr.design_guides(...)` the same way
  regardless of whether the call is in-process or HTTP. No "in-process vs remote" branching
  in business logic.
- Adding a new capability is one directory + one registry entry + one spec — not a new
  cluster service.
- Cross-service composition (variant scoring → annotation → visualization) doesn't pay
  network cost in the local regime where it would dominate latency.

**Negative / accepted trade-offs**

- Strong process isolation between services is not the default. A service that misbehaves
  (memory leak, CPU spin) can affect the API process. Mitigated by (a) heavy work going
  through the job layer (out-of-process), (b) per-service code review around resource use,
  and (c) the ability to promote a problematic service to an out-of-process worker quickly.
- Service-private dependencies (e.g. a specific Mol* version, a model runtime) live in the
  same Python environment as the agent. Mitigated by per-service optional-extras packaging
  for heavyweight deps, and by promoting such services to standalone deployments when the
  conflict becomes real.
- "Logical" boundaries demand discipline: code review must reject reach-throughs (service A
  importing service B's internals instead of calling its operations). The `Service` base
  and the registry make the correct path the easy path.

**Out of scope (deliberately not adopted)**

- A formal gRPC / Protobuf IDL for service interfaces in v1. Pydantic + Python type hints
  are sufficient; the OpenAPI document covers the remote-promotion case.
- A service mesh, sidecar, or service-discovery layer in v1. Standard env-driven config is
  enough until we have multiple promoted services in production.

## Status notes

We will revisit this if (a) a service's deployment shape demands an isolation level the
in-process model cannot give (e.g. for tenant data isolation in regime 3), or (b) the number
of capabilities grows past the point where one Python environment is a reasonable container
for all of them.
