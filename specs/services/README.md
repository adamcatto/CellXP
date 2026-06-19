# Services Specs

The **capability boundary** between the agent and the world. Each service wraps a coherent
biological/computational capability behind a typed contract so the LangGraph supervisor and
capability subgraphs (`specs/agent/capability-subgraphs/*`) can dispatch work without coupling to
specific vendors, model revisions, or transport details. Services are *logical* boundaries
(ADR-0003): they live under `src/backend/cellxp/services/<name>/` and can be promoted to
out-of-process HTTP microservices without changing the agent contract.

Every service contract MUST honor the persistence substrate defined in `specs/data/`:

- **Provenance emission** (`specs/data/provenance_model.md`) — every `Step` and substantive
  `EvidenceItem` carries `tool`, `tool_version`, `inputs` (normalized), `params`, `timestamp`,
  `input_hash`/`output_hash`, and a pointer to its output. No orphan claims.
- **Artifact storage** (`specs/data/object_storage.md`, `specs/interface/artifact_model.md`) —
  payloads above `OBJECT_INLINE_MAX` use immutable, content-addressed object storage; relational
  rows hold only metadata + storage key.
- **Audit emission** (`specs/data/audit_log.md`) — services NEVER bypass the human-review gate;
  any side-effecting or actionable output is mirrored to the audit log via the gate.

## Read in this order

| Spec | Defines | Why |
|---|---|---|
| `llm_service.md` | the reasoning-LLM provider abstraction (Ollama default, pluggable) | every node/service that calls a model passes through it |
| `reference_genome_service.md` | assemblies, sequence retrieval, coordinate normalization, liftover, entity resolution, annotation | every coordinate-dependent service depends on it |
| `alphagenome_service.md` | sequence-foundation-model + variant-effect oracle (AlphaGenome / Evo 2 class) | the primary forward predictor for regulatory/binding/splice effects |
| `binding_service.md` | motif scanning, TF binding, accessibility, occupancy deltas | composes AlphaGenome + motif DBs |
| `structure_service.md` | protein/nucleic-acid/complex/ligand-aware structure + contact maps + protein design | ESMFold/Boltz/RFdiffusion/LigandMPNN behind one boundary |
| `gwas_service.md` | trait associations, QTL lookup, LD, fine-mapping, colocalization | statistical-genetics evidence |
| `crispr_service.md` | guide design, base/prime editing, off-target enumeration, edit outcomes | **actionable**, review-gated |
| `origami_service.md` | scaffold routing, staple generation, validation, simulation, cadnano/scadnano export | **actionable**, review-gated |
| `rag_service.md` | literature/database retrieval, chunking, embedding, citation extraction | supplies citable evidence to the report generator |
| `visualization_service.md` | data→artifact normalization, composition, tile prep, exports | the data side of every interactive pane in `specs/interface/` |

## Shared contract (every service)

A service is a Python class (`Service` base, `services/base.py`) registered in
`services/registry.py`. Its operations are pure functions of validated inputs to a typed
`ServiceResult[T]`:

```python
class ServiceResult(BaseModel, Generic[T]):
    ok: bool
    value: T | None = None
    error: RunError | None = None
    steps: list[Step]                  # provenance — at least one per substantive call
    evidence: list[EvidenceItem] = []  # PROV-1 / PROV-2
    artifacts: list[ArtifactRef] = []  # ART-1..ART-10
    usage: ServiceUsage | None = None  # tokens / seconds / GPU-seconds (Budget accounting)
```

Conventions every service spec MUST follow:

- **Reject silent assumptions.** If `organism`/`assembly`/`strand`/units/Cas/PAM/edit-spec are
  missing where they matter, return a validation result that triggers an upstream `Clarification`
  (`specs/agent/state_schema.md` §7) — never guess.
- **Heavy work goes async.** Long/GPU operations emit `step.started` → `activity.update` →
  `step.finished` and dispatch via the job layer (`specs/agent/control-flow/concurrency.md`).
- **Light/deterministic calls are cached** by `(tool, tool_version, params, input_hash)`
  (`PROV-5`). Cache hits still emit a `Step` marked as cache-backed.
- **Three distinct outcomes** MUST be representable per operation: *valid empty result* (e.g. "no
  motif hits"), *unsupported* (organism/assay not covered), and *failure* (recoverable
  `RunError`). Empty ≠ unsupported ≠ failure.
- **Actionability is per-output**, not per-service. Outputs marked `ArtifactRef.actionable=true`
  create `ReviewItem`s and follow `specs/agent/human_review_policy.md`. Pure predictions are not
  gated by default unless the risk policy escalates.
- **Pluggability is config-only.** No business logic may hard-code a vendor/endpoint; backend
  selection is via env (`*_SERVICE_URL`, `LLM_PROVIDER`, …). The agent contract is invariant
  whether a service is in-process or remote.
- **Service-private code never reaches into Postgres or the object store directly** — it returns
  `Step`/`EvidenceItem`/`ArtifactRef` and lets the persistence layer write them per
  `specs/data/relational_schema.md` / `object_storage.md`.

## Capability ↔ service mapping

Each capability subgraph (`specs/agent/capability-subgraphs/*.md`) selects one or more services.
The mapping is many-to-many — the *agent* knows which capability is being executed; the *service*
knows which tool family to call. Adding a new model is a service-level change behind the same
operation signature.

| Capability | Services it composes |
|---|---|
| `variant_effect` | alphagenome, reference, binding (optional), structure (optional) |
| `gwas` | gwas, reference, rag |
| `crispr` | crispr, reference, alphagenome (inverse-design oracle), binding (off-target context) |
| `structure` | structure, reference, rag |
| `binding` | binding, reference, alphagenome |
| `annotation` | reference, rag |
| `origami` | origami, structure (optional QC), visualization |
| `rag` | rag |
| `visualization` | visualization (consumes results from all of the above) |

## Stack (from `architecture_overview.md` §4)

Python 3.11+ · Pydantic v2 typed I/O · httpx for remote service URLs · Redis (via the job layer)
for async dispatch · object store / Postgres / vector index per `specs/data/*`. Implementation
lives in `src/backend/cellxp/services/`.

## Related

`specs/data/README.md` · `documentation/explanation/architecture_overview.md` §4 ·
`documentation/reference/external_models_and_services.md` (model catalog) ·
`documentation/reference/service_registry.md` (configured backends) ·
`specs/agent/capability-subgraphs/README.md` · `specs/agent/tool_use_policy.md`.
