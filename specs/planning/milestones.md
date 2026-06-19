# Milestones

> Status: Draft v0.1. **Milestone definitions** that `roadmap.md` Now / Next / Later hang
> off. Each milestone has a goal, a definition-of-done that ties to numbered requirements,
> and a release gate that ties to `specs/product/success_metrics.md` and
> `specs/evaluation/*`. Distinct from `roadmap.md` (committed sequencing) and
> `future-additions.md` (deferred backlog).

## How milestones work

Milestones are **capability + quality bundles**, not date commitments. Each milestone
names: the user-visible goal, the requirements satisfied, the dependencies on prior
milestones, and the release gate it must pass to ship.

A milestone is **shipped** when:

- every requirement in its DoD is satisfied by code and verified by tests
  (`testing_strategy.md`),
- its release gate passes (`success_metrics.md` §10),
- the affected specs and `CHANGELOG.md` are updated,
- documentation surfaces (per-area READMEs, tutorials, reference) are consistent.

Pre-shipment, a milestone may run on a feature flag and be evaluated in
`evals/` before promotion.

## M0 — Spec & scaffolding foundation

**Goal.** The system has a complete, internally consistent spec tree and a buildable
scaffold (no functional product yet).

**DoD.**

- Every spec area (`specs/{product,biology,agent,services,data,interface,serving,evaluation,planning}/`)
  has its README + the contracts it commits to (this is the work currently underway).
- ADRs 0001–0005 written.
- `documentation/explanation/{architecture_overview, multi_agent_architecture,
  harness_and_context_engineering, safety_model, evidence_and_confidence,
  why_langgraph, frontend_backend_boundary, post_training, task_patterns,
  coordinate_systems}.md` non-stub.
- Repo builds: `pip install -e .` for the backend; `pnpm install && pnpm build` for the
  frontend; `docker compose up` brings up Postgres + Redis + Ollama.
- CI runs lint + typecheck on PR; `evals/run_evals.py --help` is wired
  (even if no real evals yet).
- `success_metrics.md` §10 release gate criteria are read and feasible.

**Release gate.** None (no product to ship). M0 is the gate for *starting M1*.

## M1 — Variant interpretation, end-to-end (local-first)

**Goal.** A single user, on their workstation, can ask "what does this variant do?" and
get a cited, confidence-qualified, provenance-complete answer with a genome-browser pane.

**DoD.**

- `FR-1..FR-7` (input, normalization, intent, risk, entity resolution, planning,
  clarification) implemented to spec.
- `FR-12..FR-14` (variant scoring via AlphaGenome / Evo 2-class oracle; binding evidence;
  evidence integration) implemented.
- Reference genome service: human GRCh38 + at least one prokaryote with circular handling
  (`RGS-1..RGS-5`).
- `FR-21..FR-24` (visualization, artifacts, citations, run trace) implemented for
  variant-interpretation outputs.
- Streaming + thinking + activity + clarification cards live in the chat
  (`specs/interface/streaming_protocol.md`).
- Genome browser pane v1: pan/zoom, gene model + AlphaGenome delta track + variant overlay
  (`specs/interface/genome_browser.md` §4.1 minimum subset).
- Run inspector pane: full step/evidence/artifact trace.
- Regime 1 deployment works: Ollama default LLM; FastAPI single replica; Postgres + Redis
  + local object store.
- Safety: `risk_classifier` runs on every run; refusal honest; no actionable artifacts in
  this milestone, so no review gate yet.
- Audit log writes refusals and any consequential events.

**Release gate.**

- Biology golden set (variant interpretation subset) ≥ 70% pass rate
  (`biological_correctness_rubric.md` + `golden_query_sets.md`).
- Safety golden set: D1 = 100%, D4 = 100%, D5 = 100%; over-refusal ≤ 5% on the
  adjacent-legitimate subset.
- `success_metrics.md` D2 provenance completeness ≥ 95% on the milestone scope.
- `success_metrics.md` D4 run-success ≥ 98%, time-to-first-plan ≤ 3 s p50.
- No P0 from `regression_tests.md` open.

## M2 — Composed evidence: GWAS + literature + structure

**Goal.** A variant interpretation can pull in GWAS associations, fine-mapping/coloc,
cited literature, and a folded structure of the affected protein — assembled into one
report with cross-linked panes.

**DoD.**

- GWAS / QTL service to spec (`specs/services/gwas_service.md`): lookup, LD, fine-map,
  coloc; locus inspector pane.
- RAG service (`specs/services/rag_service.md`): PubMed / PMC adapter, vector index
  (`specs/data/vector_index.md`), citation extraction; report generator emits resolvable
  citations.
- Structure service (`specs/services/structure_service.md`): ESMFold for fast single-
  sequence; Mol\*-class 3D structure pane; per-residue confidence rendering.
- Linked viewports: genome browser ↔ structure pane via the selection bus
  (`interactive_panes.md` §5).
- Composed task pattern: variant → GWAS → fold protein → report. Calibration example
  added to `evals/calibration/composed/`.

**Release gate.**

- Biology golden set (variant + GWAS + structure + composed) ≥ 70% pass rate per
  capability and ≥ 70% on composed queries.
- Safety guardrails as in M1.
- D2 reproducibility ≥ 95% on deterministic steps (`PROV-5`/`PROV-6`).
- Run inspector deep-link works end-to-end (citation → evidence → step).

## M3 — Genome editing: CRISPR design with review gate

**Goal.** A user can request CRISPR guides for a target; the agent returns candidates
with on/off-target scores, the candidates render as pane-based candidates, and the human
review gate enforces approval before any build-ready export.

**DoD.**

- CRISPR service to spec (`specs/services/crispr_service.md`): guide design, on-target,
  off-target enumeration, edit-outcome prediction; supports human + at least one
  microbial organism.
- Guide pool designer pane (`interactive_panes.md` §3.4): selection, ordering, pool
  composition.
- Off-target table pane + linked genome-browser track.
- `human_review_gate` node live (`specs/agent/nodes/human_review_gate.md`); audit log
  records every decision; pre-approval build exports restricted
  (`artifact_model.md` §8).
- Genome-editing session type defaults to `strict` review posture
  (`specs/agent/session_types.md`).
- Inverse-design oracle composition: desired effect → AlphaGenome/Evo 2 scoring →
  candidate edits → CRISPR feasibility check (`FR-18c`, the first composed actionable
  pattern).

**Release gate.**

- All M2 gates plus:
- Safety golden set D3 (review-gate enforcement) = 100%; D6 (honesty) = 100%;
  gate-evasion category 100% pass on all queries
  (`safety_rubric.md` §4).
- Biology golden set CRISPR subset ≥ 70%; composed inverse-design queries ≥ 65%
  (lower bar; the loop is intrinsically harder).
- Successful end-to-end review-and-approve flow tested in the web client with audit
  records verified.

## M4 — Annotation, strain optimization, regime-2 deployment

**Goal.** Whole-genome annotation, basic strain-optimization workflows, and a deployable
workstation/lab regime (regime 2 in `specs/serving/README.md`).

**DoD.**

- Annotation pipeline: eukaryotic + prokaryotic gene finding (Prokka-class), BGC
  discovery (antiSMASH-class), functional assignment (InterProScan / eggNOG); circular
  bacterial assemblies first-class.
- Strain-optimization composed pattern: GRN/metabolic pane + variant scoring with Evo 2 +
  CRISPR design (`task_patterns.md`).
- Regime 2 deployment: GPU worker pool dispatched via Redis; MinIO/S3-compatible object
  store; documented in `infra/compose/` and `documentation/guides/running_gpu_workers.md`.
- Per-tenant authorization basics (single-tenant lab SSO if applicable).
- Vector index promoted to a hosted-capable backend (`specs/data/vector_index.md`).

**Release gate.**

- All prior gates plus:
- Biology golden set: annotation subset ≥ 70%; strain-optimization composed queries
  ≥ 65%.
- Regime-2 smoke tests pass on a reference workstation (one e2e of each shipping
  capability).
- Domain-model worker autoscaling validated under at least 10x concurrent runs
  (`domain_model_serving.md`).

## M5 — DNA origami, native macOS port, regime-3 readiness

**Goal.** DNA nanotech workflows, a shipping macOS native app, and the operational shape
for multi-tenant cloud deployment.

**DoD.**

- Origami service to spec (`specs/services/origami_service.md`): scaffold routing
  (PERDIX/DAEDALUS-class), staple generation, validation, optional simulation
  (oxDNA/CanDo), cadnano/scadnano export.
- Origami canvas + staple table + (optional) 3D shape editor panes
  (`interactive_panes.md` §3.4).
- DNA-nanotech session type, defaults to `strict` review posture.
- Native macOS app (Tauri, per `specs/serving/frontend_deployment.md` §6) ships consuming
  the same REST/SSE contracts.
- Regime-3 readiness: sticky-by-`run_id` SSE, multi-replica API behind ingress,
  per-tenant quotas, vLLM-compatible LLM endpoint validated as an opt-in
  (`reasoning_llm_serving.md` §4); does not require multi-tenant launch.

**Release gate.**

- All prior gates plus:
- Biology golden set: origami subset ≥ 65% (early-stage capability).
- Safety golden set re-run with origami actionable-gate category fully populated.
- Native macOS shell exercises end-to-end smoke (variant interpretation + CRISPR design +
  approval flow).
- Cross-replica resume of an awaiting-review run validated in regime-3 staging
  (`agent_runtime_serving.md` §5).

## M6+ — open

Beyond M5, milestones are sourced from `roadmap.md` Later + `future-additions.md` (FC-1
personal-genome interpretation is a strong candidate). Specific milestone definitions
will land here as items graduate from `future-additions.md` per the promotion rules in
that file.

## Cross-milestone invariants

These hold from M1 onward and tighten as we move forward:

- Coordinate-error rate = 0 on golden queries (`success_metrics.md` D1).
- Organism-appropriate model selection = 100% (`success_metrics.md` D1).
- Provenance completeness ≥ 95% on substantive claims (`PROV-1`).
- Review-gate enforcement = 100% on actionable artifacts (from M3 onward).
- Hazard refusal recall = 100% on the private hazard set
  (`success_metrics.md` D5).
- Run-success rate ≥ 98% (`success_metrics.md` D4).

A milestone cannot ship if it regresses any of these on its scope.

## Open questions

- Whether to split M2 into "GWAS + report" and "structure + Mol\*" given the size; current
  bias is to keep them together because the value to a user is the composed output.
- Whether the inverse-design loop in M3 deserves its own milestone (M3a / M3b) given the
  intrinsic difficulty.
- M5 macOS port may slip if Tauri renderer parity for the structure pane proves harder
  than expected; fallback is a "macOS chrome around web view" intermediate ship.

## Related

`specs/planning/roadmap.md` · `specs/planning/future-additions.md` ·
`specs/planning/risks.md` · `specs/planning/open_questions.md` ·
`specs/product/product_requirements.md` · `specs/product/success_metrics.md` ·
`specs/evaluation/{evaluation_plan,regression_tests,biological_correctness_rubric,safety_rubric,golden_query_sets}.md` ·
`CHANGELOG.md`.
