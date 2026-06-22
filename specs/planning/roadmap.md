# Roadmap

> Status: **Draft v0.1 — populated.** This is the **near-term, committed plan**: what we'll build
> next and in roughly what order. The foundational spec set has landed (M0 spec tree complete; product
> is still scaffold), so the horizons below sequence real, scoped work instead of guesses.
>
> For the planning model and where things go, see "How planning is organized" below. For *how this
> work parallelizes across simultaneous agent sessions*, see "Execution waves" at the end.
>
> **Implementation checkpoint (2026-06-22):** The deployment-completion wave landed Postgres-backed
> API/run persistence and LangGraph checkpoints, Redis Streams job primitives, S3-compatible object
> storage, pinned ESMFold/Boltz-2 GPU workers, production GWAS/QTL and CRISPR worker transports,
> opt-in live tests, and Playwright chat/clarification/review journeys. The fail-closed M1–M3 gate
> report remains **blocked**: the public biology catalogs are seed-sized and unscored, authorized
> private hazard-set scores are unavailable, and live GPU/CRISPR deployment evidence has not been
> produced. Do not start L1 or promote L3 until those gates pass. See
> `evals/reports/m1-m3-gate-report-2026-06-22.json`.

## How planning is organized

Planning lives in three coordinated docs, split by **commitment** (not just time):

| Doc | Holds | Commitment |
|---|---|---|
| `roadmap.md` (this) | near-term work, sequenced as **Now / Next / Later** | committed / directional |
| `future-additions.md` | deferred scope, exploratory directions, future-capability backlog (`FC-*`) | **not** committed |
| `milestones.md` | milestone definitions (M1, M2, …) that Now/Next/Later hang off | — |

Supporting: `open_questions.md` (unresolved decisions) and `risks.md` (what could go wrong).

**Flow:** ideas enter `future-additions.md` → graduate **into this roadmap** (Now/Next/Later) when
they're prioritized, scoped enough to estimate, and prerequisites are known → become `FR-*` +
capability/biology specs when picked up. Status vocabulary is shared across docs:
`idea → exploring → committed → in-progress → shipped` (or `deferred`).

## Horizons

Each item uses a one-line schema: **what · why · status · depends-on · target milestone**. IDs
(`N*`/`X*`/`L*`) are stable handles referenced by "Execution waves" below.

### Now
<!-- The current focus: scoped, specced, dependencies known. Closing M0 + the M1 spine and first slice. -->

- **N1 — Close M0.** Spec consistency pass + buildable scaffold + CI green · unblocks all code ·
  *shipped* · depends-on: — · M0.
- **N2 — Foundation contracts (the frozen spine).** `domain/` (coordinates, validators, models,
  evidence, errors, enums), `agent/state.py`, `services/base.py` + `registry`, storage/provenance
  models, `artifact_model`, `streaming_protocol` + `api_contracts` · the shared contracts every
  downstream slice imports; structurally mitigates R2 (coordinates) and R3 (provenance) ·
  *shipped* · depends-on: N1 · M1.
- **N3 — Core orchestration pipeline.** normalizer → intent → risk → entity → planner → clarify
  (FR-1..FR-7) · the agent loop all subgraphs hang off · *in-progress* (implementation, graph
  integration coverage, ordered SSE/replay/pause-resume, durable Postgres repository/checkpoint
  wiring, and browser coverage complete; moving graph execution off the API process through the
  Redis queue remains) · depends-on: N2 · M1.
- **N4 — Reference genome service.** GRCh38 + ≥1 prokaryote with circular handling (RGS-1..RGS-5) ·
  coordinate source of truth; R2/R4 mitigation · *shipped* (catalog + 6 operations, Ensembl
  gene/dbSNP resolution and cross-assembly mapping, circular handling, and deterministic tests;
  upstream availability remains a deployment concern) ·
  depends-on: N2 · M1.
- **N5 — Variant-effect vertical slice.** `variant_effect` subgraph + AlphaGenome service + binding
  evidence + evidence integration + report/run-trace (FR-12, FR-13, FR-14 binding subset, FR-22..24) ·
  proves the architecture end-to-end; first proven contract before fan-out · *in-progress*
  (AlphaGenomeService + BindingService + variant_effect subgraph + evidence integration, Ensembl
  resolution, strict remote AlphaGenome/Evo 2 worker transport, and model-call provenance complete;
  pinned worker images/weights and live-model acceptance remain) ·
  depends-on: N3, N4 · M1.
- **N6 — Frontend M1.** chat + progressive streaming UI, genome-browser pane v1, run inspector
  (FR-21, FR-27, FR-30) · the user-visible surface · *in-progress* (wire types, REST+SSE client,
  streaming accumulator, chat thread, genome browser, run inspector, workspace layout, locus and
  linked structure panes, guide/off-target panes, app pages, and Playwright streaming,
  clarification, review/approve, and accessibility journeys implemented; candidate persistence and
  the full Mol* mmCIF dependency remain) ·
  depends-on: N2 (contracts only) · M1.
- **N7 — Safety M1.** `risk_classifier` on every run + audit log of refusals/consequential events
  (FR-33, FR-34) · R1 structural defense · *shipped* (AuditEntry domain model + SHA-256 hash
  chain; AuditLog ORM table + AuditRepository; safety.refused/restricted wired into
  risk_classifier; human_review_gate implemented with review.requested/decided/actionable.emitted;
  16 unit tests covering AL-1..6; X6 will wire the gate into the graph for actionable outputs)
  · depends-on: N2 · M1.

### Next
<!-- Committed and sequenced, not started. Theme/epic granularity. -->

- **X1 — GWAS/QTL.** service + subgraph + locus-inspector pane (FR-14) · associations, LD, fine-map,
  coloc · *in-progress* (typed `GwasService` with injectable backend, four operations, human-data
  coverage guards, provenance/artifacts, GWAS subgraph, tests, locus-inspector pane, direct EBI
  GWAS/eQTL adapter, and versioned statistical-worker transport complete; additional Open Targets,
  LD-panel, and pinned SuSiE/coloc worker deployment remains) · depends-on: N5 · M2.
- **X2 — RAG.** service + vector index + report-resolvable citations (FR-20) · literature grounding;
  R3 citation validity · *in-progress* (five-operation `RagService`, injectable retrieval/vector
  backend contract, RAG subgraph, citation maps, PubMed/PMC adapter, persistent SQLite vector index,
  and local ingestion/retrieval composition complete; production-scale index and selected embedding
  model remain deployment choices) · depends-on: N5 · M2.
- **X3 — Structure.** ESMFold service + Mol\*-class 3D pane + linked viewports (FR-18) · folded-protein
  evidence · *in-progress* (StructureService with ESMFold/Boltz-2/Orca/DNAshapeR backend protocol +
  `predict_structure`/`predict_contacts`/`predict_dna_shape`, structure subgraph, tests, and linked
  PDB 3D/confidence pane with Mol* seam, pinned ESMFold/Boltz-2 GPU worker, immutable model-download
  flow, mmCIF artifact production, and opt-in live smokes complete; release-gate live execution and
  durable Redis dispatch remain) · depends-on: N5 · M2.
- **X4 — Composed evidence pattern.** variant → GWAS → fold → report + calibration eval · the M2
  user-visible payoff · *shipped* (ordered dependency plan, cross-subtask evidence accounting,
  planner tests, golden query, and worked calibration example) · depends-on: X1, X2, X3 · M2.
- **X5 — CRISPR design.** service + subgraph + guide-pool & off-target panes (FR-15) · first actionable
  capability · *shipped* (typed four-operation service, injectable backend, organism/assembly and
  edit-spec guards, actionable artifacts, subgraph, deterministic coverage, and guide/off-target
  panes plus a versioned scoring/off-target worker transport; pinned worker deployment and persisted
  pool composition remain deployment work) ·
  depends-on: N5 · M3.
- **X6 — Human-review gate.** `human_review_gate` node + genome-editing session type (strict posture)
  (FR-25, FR-26, FR-39) · R1; enforced before any build-ready export · *shipped* (supervisor
  routing, durable approval resume with stable review IDs, actionable artifact/subtask coverage,
  and executable strict session defaults) · depends-on: X5, N7 · M3.
- **X7 — Inverse-design oracle.** desired effect → forward-model score → candidate edits → CRISPR
  feasibility (FR-18c) · first composed actionable loop · *shipped* (typed bounded optimizer,
  injectable joint oracle/feasibility backend, weighted/Pareto ranking, partial-target reporting,
  actionable subgraph and supervisor routing, deterministic tests) · depends-on: X5, X6 · M3.

### Later
<!-- Directional themes we're confident about; no commitment to the "how" yet. -->

- **L1 — Annotation pipeline.** euk + prok gene finding, BGC discovery, functional assignment (FR-16) ·
  circular assemblies first-class · *committed* · depends-on: N4 · M4.
- **L2 — Strain optimization + networks/GEM.** GRN/metabolic composed pattern (FR-18d) · *exploring* ·
  depends-on: L1, X5 · M4.
- **L3 — Regime-2 deployment.** GPU worker pool (Redis), MinIO/S3 object store, hosted-capable vector
  index · workstation/lab regime · *committed* · depends-on: X3 · M4.
- **L4 — Protein function & design / metabolites.** FR-18a, FR-18b · *exploring* · depends-on: X3 · M4.
- **L5 — DNA origami.** service + canvas/staple panes + cadnano export (FR-19) · *committed* ·
  depends-on: X6 · M5.
- **L6 — Native macOS (Tauri).** ships against the same REST/SSE contracts · *committed* (R9 slip
  risk; fallback = chrome-around-webview) · depends-on: N6 · M5.
- **L7 — Regime-3 readiness.** multi-replica API, sticky-by-`run_id` SSE, per-tenant quotas, vLLM
  opt-in · *committed* · depends-on: L3 · M5.
- **L8 — FC-1 personal-genome interpretation (flagship).** batch variant path + PRS/ancestry/PGx,
  research-grade · *idea* — needs batch processing + strong privacy/consent controls · depends-on:
  L1, X1, X2 · M6+.
- **L9 — Reasoning-LLM post-training (SFT/DPO/RLVR).** offline track, never in-product · *exploring* ·
  depends-on: N5 (for trace data) · target: parallel track (`specs/training/post_training.md`).

## Execution waves (parallelization across simultaneous agent sessions)

The architecture is built to fan out: **freeze the shared contracts, then build verticals in
parallel.** The hard rule for concurrent sessions is **one session = one directory subtree, importing
only frozen contracts** — so sessions never edit the same files.

- **Wave 0 — contract freeze (serialize; ≤2 sessions).** N2. `domain/`, `agent/state.py`,
  `services/base.py` + `registry`, storage/provenance, `artifact_model`, `streaming_protocol` +
  `api_contracts`. Everything downstream imports these; they must stabilize *before* fan-out. After
  this wave these files are **frozen** — changing them is a coordinated mini-cycle, never an ad-hoc
  edit inside a feature session.
- **Wave 1 — spine (2 parallel sessions).** (a) graph skeleton + core nodes (N3); (b) reference
  service (N4). Land the **visualization service + artifact registry early here** — many panes depend
  on it.
- **Critical path: N2 → N5 is serial.** Prove the variant-effect vertical end-to-end before fanning
  out the other backend slices, so a contract flaw isn't baked into eight sessions at once.
- **Wave 2 — full fan-out (independent simultaneous sessions).** Backend verticals (one session each:
  variant_effect, gwas, rag, structure, crispr, binding, annotation, origami — subgraph + service +
  tests + golden set per session); frontend panes (chat/streaming, genome browser, structure, plots,
  run inspector, workspace shell — depend only on `api_contracts` + `streaming_protocol` +
  `artifact_model`); per-capability evals trailing each capability.

**Two coordination hazards (design for these now):**

1. **The registry is the one shared mutable point** — use append-only / entry-point registration so
   two sessions adding services don't conflict (also mitigates R7 taxonomy sprawl).
2. **`human_review_gate` (X6) touches core nodes**, not just its own subtree — sequence it as a small
   coordinated change, not a free parallel session.

## Related

`future-additions.md` · `milestones.md` · `open_questions.md` · `risks.md` ·
`specs/product/product_requirements.md` · `specs/product/mission.md` · `CONTRIBUTING.md`.
