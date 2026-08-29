# Architecture Overview & Canonical Tech Stack

> Status: Draft v0.1. This is the **single source of truth** for the technology stack and the
> high-level system architecture. Every other spec (services, interface, data) MUST use the
> technologies and boundaries described here. Versions track `pyproject.toml`,
> `src/frontend/package.json`, and `docker-compose.yml`; when they drift, those manifests win and
> this doc should be updated.

## 1. System at a glance

CellXP has four logical tiers:

1. **Frontend** — a Next.js chat-driven workspace using CopilotKit v2 for agent chat and CellXP
   renderers for typed scientific panes.
2. **API / agent runtime** — FastAPI hosting canonical REST/SSE, AG-UI projection, a
   harness-neutral skill/policy kernel, and pluggable mature-harness adapters.
3. **Skills / services** — specialized biological capabilities (variant effect, GWAS, CRISPR, structure,
   binding, annotation, RAG, visualization, origami), invoked by the agent.
4. **Infrastructure** — Postgres (state/metadata), Redis (queue + cache), object storage
   (artifacts), a vector index (RAG), and GPU workers (heavy models).

```
                       ┌──────────────────────────────────────────────┐
                       │                Frontend (Next.js)             │
                       │   chat • workspace • artifacts • run inspector │
                       └───────────────┬───────────────▲──────────────┘
                          HTTPS / REST │      SSE      │ stream
                                       ▼               │
                       ┌──────────────────────────────────────────────┐
                       │             API + Agent Runtime (FastAPI)     │
                       │  AG-UI • policy kernel • harness adapter      │
                       └───┬───────────────┬───────────────┬──────────┘
                           │               │               │
              in-process / RPC      enqueue (Redis)   read/write
                           │               │               │
            ┌──────────────▼───┐   ┌───────▼───────┐  ┌────▼─────────────────────┐
            │ Skills/services  │   │  Job workers  │  │  Storage                  │
            │ variant • gwas   │   │ CPU + GPU     │  │ Postgres • Redis          │
            │ crispr • struct  │   │ (Boltz/ESM…)  │  │ object store • vector idx │
            │ binding • rag …  │   └───────────────┘  └───────────────────────────┘
            └──────────────────┘
```

For the harness decision and frontend/backend line, see ADR-0008 and
`frontend_backend_boundary.md`. `why_langgraph.md` documents the compatibility graph's original
rationale. Diagrams live in
`documentation/diagrams/`.

## 2. Backend stack

| Concern | Choice | Version (floor) | Notes |
|---|---|---|---|
| Language | Python | 3.11+ | `requires-python = ">=3.11"` |
| Web framework | FastAPI | 0.115+ | REST + SSE; async-first |
| ASGI server | Uvicorn (standard) | 0.30+ | `uvicorn[standard]` |
| Validation / schemas | Pydantic v2 | 2.7+ | all domain models + API I/O |
| Settings | pydantic-settings | 2.3+ | env-driven config |
| HTTP client | httpx | 0.27+ | calls to model microservices |
| Agent skill/policy kernel | CellXP contracts | internal | typed plugins + non-bypassable policy (ADR-0008) |
| Mature harness | Qwen Code | evaluation target | SDK/headless adapter; pinned version after evaluation |
| Compatibility workflows | LangGraph | 0.2+ | existing supervisor/subgraphs during migration |
| LLM primitives | langchain-core | 0.3+ | messages, tool interfaces |
| ORM | SQLAlchemy | 2.x | typed, async-capable |
| Postgres driver | psycopg | 3.2+ | `psycopg[binary]` |
| Cache / broker | redis-py | 5+ | cache + job queue |
| Lint / format | Ruff | 0.6+ | line length 100 |
| Types | mypy | 1.10+ | |
| Tests | pytest | 8+ | `tests/` (unit/integration/e2e) |

**Packaging.** setuptools; distribution name `cellxp`, import package
`cellxp`, sources under `src/backend` (ADR-0001).

### LLM providers

Harness adapters and LLM-backed skills (intent/risk/entity/planning/critique/reporting) call an LLM
behind a thin **provider abstraction** — the **LLM service** (`specs/services/llm_service.md`).
The product is provider-pluggable; no business logic may hard-code a single vendor or endpoint.

- **Local-first default: Ollama.** The default deployment serves a local open-weight model via
  **Ollama** (`OLLAMA_BASE_URL`, `LLM_MODEL`), so the system runs fully offline/self-hosted with no
  external API dependency or key — important for private sequence data (`NFR-7`) and reproducibility.
- **Pluggable remote providers.** Hosted providers (OpenAI-compatible, Anthropic, etc.) are
  selectable via env for higher-capability models without code changes.

Prompt/skill assets are versioned under the adapter or skill that owns them (legacy assets remain in
`src/backend/cellxp/agent/prompts/`). Note this is the **reasoning
LLM** (the agent's "brain"); it is distinct from the domain **foundation models** (AlphaGenome, Evo2,
ESMFold, …) catalogued in `documentation/reference/external_models_and_services.md`.

## 3. Frontend stack

| Concern | Choice | Notes |
|---|---|---|
| Framework | Next.js (App Router) | `src/frontend/app/` |
| Language | TypeScript | strict |
| UI runtime | React | function components, hooks |
| Styling | Tailwind CSS | `tailwind.config.ts`, `globals.css`, `styles/theme.css` |
| Component primitives | local `components/ui/*` (Button, Card, Dialog, Tabs) | shadcn/ui-style, headless + Tailwind |
| Agent UI/runtime | CopilotKit v2 (OSS) + AG-UI | chat shell, tool rendering, shared state, generative UI; ADR-0006 |
| Streaming | SSE via `fetch`/`EventSource` | `lib/streaming.ts` |
| Data fetching | typed client in `lib/api.ts` | thin wrapper over REST |
| 3D structure | Mol* (recommended) | `components/structure/StructureViewer3D.tsx` |
| Genome tracks | custom Canvas/SVG | `components/genome/*` (see `specs/interface/genome_browser.md`) |
| Scientific plots | visx / D3 primitives (recommended) | `components/plots/*` (locus, contact map, motif logo, delta track) |

> Recommended libraries (Mol*, visx) are defaults, not yet locked. Lock them in
> `specs/interface/*` before implementation. The frontend `package.json` currently pins only
> Next/React; visualization deps are added when those specs land.

The chat-vs-workspace UX paradigm, panels, and component contracts are specified in
`specs/interface/` (`workspace_interface.md`, `chat_interface.md`, `artifact_model.md`,
`genome_browser.md`, `api_contracts.md`).

CopilotKit is an **experience layer**, not a scientific or persistence boundary. The browser calls a
same-origin Next.js CopilotKit runtime route, which brokers AG-UI to FastAPI. FastAPI maps AG-UI
events to canonical CellXP runs, steps, evidence, artifacts, and runtime interrupts. Native/CLI
clients continue to consume CellXP REST/SSE directly. CopilotKit Enterprise Intelligence is optional
and is not the v1 source of truth for sessions or checkpoints (`ADR-0006`,
`specs/planning/copilotkit_integration.md`).

## 4. Services layer

Services are **logical boundaries** (ADR-0003): each lives under
`src/backend/cellxp/services/<name>/` with a uniform interface (`services/base.py`,
registered in `services/registry.py`). They are callable in-process for light/CPU work and can be
promoted to standalone HTTP microservices for heavy/GPU work without changing the agent contract.
Service URLs are already enumerated in `.env.example`
(`ALPHAGENOME_SERVICE_URL`, `STRUCTURE_SERVICE_URL`, `GWAS_SERVICE_URL`, `CRISPR_SERVICE_URL`).

| Service | Dir | Representative external models/data |
|---|---|---|
| Variant effect | `services/alphagenome/` | AlphaGenome / Evo2-style predictors |
| GWAS / QTL | `services/gwas/` | GWAS Catalog, Open Targets, LD, fine-mapping |
| CRISPR | `services/crispr/` | on/off-target scoring, base & prime editing |
| Structure | `services/structure/` | ESMFold/Boltz-style, DNA shape, contact maps |
| Binding | `services/binding/` | motif scan, footprinting, occupancy deltas |
| Annotation / reference | `services/reference/` | assemblies, gene models, liftover |
| RAG | `services/rag/` | PubMed + DB retrieval, citation extraction |
| Visualization | `services/visualization/` | server-side artifact/figure generation |
| Origami | `services/origami/` | scaffold/staple design, cadnano export |

Per-service contracts live in `specs/services/`; biological methodology in `specs/biology/`.

## 5. Agent runtime, skills, and policy

The target architecture is a **mature harness over a CellXP-owned skill and policy kernel**
(ADR-0008):

1. A `HarnessAdapter` translates a harness turn and events to the canonical CellXP run model.
   Qwen Code SDK/headless streaming is the first adapter target because it already supplies coding,
   skills, sub-agents, memory, MCP, hooks, and local OpenAI-compatible model support.
2. Versioned `SkillPlugin`s expose bounded Pydantic inputs and provenance-bearing results. Domain
   logic stays in `services/*`; reusable deterministic workflows may be skill implementations.
3. The policy kernel wraps every invocation outside the harness and enforces risk clearance,
   authorization, coordinates, budgets, provenance, sandbox scope, and actionable-output review.
   Harness-native hooks mirror policy for quick feedback but are not an authorization boundary.
4. Canonical storage and AG-UI remain stable if the harness changes.

The implemented LangGraph supervisor (`agent/graph.py`) remains a compatibility workflow while
capabilities are extracted. `harness/langgraph_compat.py` constructs a minimal legacy state slice
from typed skill input; it never publishes raw `AgentState` as a model tool. See
`specs/agent/skill_plugin_contract.md`, `harness_and_context_engineering.md`, and
`specs/agent/graph_spec.md` (compatibility contract).

### 5.1 Orchestrating foundation models (Evo2 / AlphaGenome / ESMFold / Boltz-2 / …)

The agent's core job is **model orchestration**: choosing which predictive model to run, preparing
its inputs correctly, dispatching it, and fusing its outputs into the evidence stream. The agent
treats each model as a tool behind a service interface — it does not embed model weights or
inference code in the graph itself.

> The authoritative, comprehensive inventory of orchestratable models, tools, and data services
> (across sequence/variant, splicing, protein & nucleic-acid structure, chromatin/shape, TF binding,
> annotation incl. prokaryotic, GWAS/QTL, CRISPR, protein/sequence design, docking/cheminformatics,
> DNA origami, RAG, and single-cell) lives in
> `documentation/reference/external_models_and_services.md`. The table below is only an illustrative
> slice of the highest-priority models.

Key behaviors:

- **Model selection by task + input + organism.** The planner/task-selector maps an intent to one or
  more candidate models, picking by what the input affords and what the question needs. Rough mapping:

  | Need | Primary model(s) | Service |
  |---|---|---|
  | Variant regulatory/functional effect (assay/tissue-resolved) | **AlphaGenome** | `services/alphagenome/` |
  | Long-range sequence modeling, generative/zero-shot variant & sequence scoring, cross-species (incl. microbial) | **Evo2** | `services/alphagenome/` (sequence-model client) |
  | Single-sequence protein structure (fast) | **ESMFold** | `services/structure/` |
  | Complex / multimer / protein–ligand / nucleic-acid-aware structure (higher fidelity) | **Boltz-2** | `services/structure/` |
  | DNA shape, nucleosome, chromatin contacts | shape/contact predictors | `services/structure/` |

  Where models overlap (e.g. ESMFold vs Boltz-2 for a monomer, or AlphaGenome vs Evo2 for variant
  scoring), the agent picks a sensible default by latency/cost/fidelity and **surfaces the choice**;
  it MAY ask the user when the trade-off is consequential (see `specs/agent/tool_use_policy.md`).

- **Input adaptation per model.** Each model has different requirements — sequence window/context
  length, alphabet, masking, assembly/coordinate framing, multimer/ligand specification. The
  relevant service (and `agent/nodes/input_normalizer.py` + `entity_resolver.py`) is responsible for
  shaping normalized inputs into each model's expected form, including organism-specific framing
  (e.g. circular bacterial coordinates) so a human-trained context window is never silently misused
  on a microbial genome.

- **Composition / chaining.** Skills feed each other through durable typed results: e.g. annotate a locus → score a variant with
  AlphaGenome/Evo2 → predict the affected protein's structure with ESMFold/Boltz-2 → visualize. The
  harness sequences these as dependent subtasks and carries intermediate outputs by bounded state
  and artifact/evidence handles.

- **Closed-loop / inverse design.** Beyond linear chains, the agent supports goal-directed loops that
  *invert* forward models: given a desired functional effect, it proposes candidate edits, scores
  them with a forward effect oracle (AlphaGenome/Evo2) plus off-target/feasibility penalties (CRISPR
  tools), and iterates an optimizer (greedy/evolutionary/gradient-guided) toward a multi-objective of
  maximal on-target effect with minimal off-target/collateral impact. This is the **model-guided edit
  design** capability (`FR-18c`; catalog §11) and is the canonical example of the agent composing
  predictors + design tools + search into one run. Actionable → review-gated.

- **Systems-level composition across scales.** The same machinery composes models from sequence →
  molecule → network → phenotype: variant→gene-regulatory-network impact, variant→metabolism in
  bacterial strains, metabolic-network reconstruction + flux analysis, and full strain/pathway
  engineering (`FR-18d`/`FR-18c`). These multi-stage recipes — including organism-appropriate oracle
  selection (mammalian AlphaGenome vs prokaryote Evo 2) and cross-chain uncertainty propagation — are
  documented as a cookbook in `documentation/explanation/task_patterns.md`.

- **Heavy inference is async.** ESMFold/Boltz-2 and other GPU models run as jobs (Redis queue + GPU
  workers, §7); the agent dispatches, streams liveness, and integrates results when ready rather than
  blocking the run.

- **Provenance per model call.** Every model invocation records the model identity, version/weights,
  parameters, and inputs into the run trace, and every prediction carries confidence (e.g.
  per-residue pLDDT-style scores for structure, calibrated/qualitative bands elsewhere) — satisfying
  `FR-24`/`FR-23` and `evidence_and_confidence.md`.

- **Pluggability.** Adding or swapping a model (new predictor, updated Evo2/Boltz revision) is a
  service-level change behind the same tool contract; the orchestration graph does not change
  (`NFR-11`, ADR-0003). External model endpoints are configured via env (`*_SERVICE_URL`).

### 5.2 Reasoning model and long-horizon harness

The target capable-GPU quality profile uses `Qwen/Qwen3.8-27B` through a provider-agnostic
OpenAI-compatible service, with per-role reasoning budgets and schema-validated tool output.
Modest-hardware local deployments retain a smaller explicit profile; no 27B download or remote
fallback is silent. Qwen Code is the first mature harness adapter target and all file/code/shell
work runs in an isolated per-run sandbox. Prime Agent and Hermes remain comparison/reference
designs (`ADR-0007`, ADR-0008, `specs/planning/copilotkit_integration.md`).

## 6. Data & storage

| Store | Tech | Holds |
|---|---|---|
| Relational | Postgres 16 | runs, messages, artifacts metadata, audit log, users |
| Cache / queue | Redis 7 | job queue, result cache, rate limits, ephemeral run state |
| Object storage | pluggable (`OBJECT_STORE_URL`; `file://` dev, S3-compatible prod) | large artifacts: structures, plots, track data |
| Vector index | pluggable | RAG embeddings + chunks |

Connection strings come from env (`.env.example`). Schemas: `specs/data/` and
`documentation/diagrams/database_schema.mmd`. Coordinate-system conventions:
`coordinate_systems.md` (treated as a correctness-critical invariant).

## 7. Jobs & compute

Long-running / GPU work (structure prediction, large model inference) is dispatched to workers via
Redis (`jobs/queues.py`, `jobs/worker.py`, `jobs/tasks.py`, `jobs/gpu.py`). The API stays
responsive; results stream back to the run as they complete. GPU workers are deployed separately
(`infra/k8s/worker-deployment.yaml`, `infra/compose/docker-compose.gpu.yml`; see
`running_gpu_workers.md`).

## 8. Deployment & infra

- **Local dev**: `docker-compose.yml` (Postgres + Redis) + `scripts/dev_api.sh` /
  `scripts/dev_frontend.sh`.
- **Containers**: `infra/docker/{api,worker,frontend}.Dockerfile`.
- **Compose stacks**: `infra/compose/docker-compose.yml` (+ `.gpu.yml`).
- **Kubernetes**: `infra/k8s/` (api, worker, frontend, postgres, redis, ingress).
- **IaC**: `infra/terraform/` (placeholder).
- **CI/CD**: `.github/workflows/` (ci, docker, evals).

## 9. Cross-cutting concerns

- **Config**: env-driven via pydantic-settings (`config/settings.py`); never hard-code secrets.
- **Provenance & audit**: every run, tool call, and artifact is persisted and addressable
  (`specs/data/provenance_model.md`, `specs/data/audit_log.md`).
- **Safety**: kernel-enforced risk clearance before biological skills + human review before
  actionable release (`safety_model.md`, ADR-0005, ADR-0008).
- **Evidence & confidence**: standardized evidence objects + confidence reporting
  (`evidence_and_confidence.md`).
- **Evaluation**: golden queries + rubrics gate releases (`evals/`, `specs/evaluation/`).

## 10. Key architectural decisions (ADR index)

- ADR-0001 — unified `src/` layout (backend + frontend in one repo).
- ADR-0002 — LangGraph supervisor with subgraphs.
- ADR-0003 — keep service boundaries logical (promote to microservices only when needed).
- ADR-0004 — specs are development contracts.
- ADR-0005 — human review for actionable biology.
- ADR-0006 — CopilotKit over a CellXP-owned AG-UI adapter.
- ADR-0007 — adopt Qwen3.8 as the quality model (harness portion superseded).
- ADR-0008 — harness-neutral skill/policy kernel; Qwen Code is the first adapter target.
