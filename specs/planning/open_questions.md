# Open Questions

> Status: Draft v0.1. The **cross-spec index of unresolved decisions** — meta-questions that
> span more than one spec, plus pointers into each spec's local *Open questions* section.
> Distinct from `risks.md` (threats with mitigations) and `future-additions.md` (deferred
> scope). An item here is something we will need to *decide*, not something we will need to
> *defend against* (risks) or something we have already decided to *defer* (future-additions).

## How this document works

Every CellXP spec ends with an *Open questions* section listing the local unresolved
decisions in that area. This file is the **index over all of those** plus a small set of
**cross-cutting questions** that no individual spec is the right home for.

Each entry below:

- States the question in one sentence.
- Names the leading candidate and the trade-off.
- Lists the specs that depend on the answer.
- Has a status: `open` (no decision) · `leaning <option>` (provisional preference)
  · `decided` (move to an ADR; remove from this file).

Items graduate **out** of this file when they become an ADR or are resolved with a spec
change that no longer leaves room for ambiguity.

## A. Cross-cutting meta-questions

### A1 — Cross-run object-store CAS dedupe scope

- **Question.** Is the content-addressed object store global per deployment, per tenant,
  or per session?
- **Trade-off.** Global maximizes dedupe (a Boltz prediction on the same input bytes is
  computed once) and minimizes cost; per-tenant preserves stronger isolation; per-session
  is the strictest privacy posture but loses essentially all dedupe benefit.
- **Leaning.** *Per-tenant in regime 3; deployment-global in regimes 1–2.* Need a written
  policy and a CAS-key prefix per scope.
- **Affects.** `specs/data/object_storage.md` §9.1, `specs/data/provenance_model.md` §10,
  regime-3 capacity planning.
- **Status.** `open`.

### A2 — Per-role reasoning-LLM defaults in regime 3

- **Question.** Which roles (planner, critic, report writer, entity resolver, ...) get a
  larger model out of the box in regime 3, and which stay on the default?
- **Trade-off.** Stronger planner / report writer improves D1/D5 metrics; cost climbs
  linearly; model heterogeneity makes provenance read noisier.
- **Leaning.** Planner + report writer one tier up; everything else on default.
- **Affects.** `specs/services/llm_service.md` §5, `specs/serving/reasoning_llm_serving.md`
  §5, `success_metrics.md` D1/D2 baselines.
- **Status.** `open`.

### A3 — Embedding model selection and re-embedding policy

- **Question.** Which embedding model is the default for RAG, and what triggers a full
  re-embed of the vector index?
- **Trade-off.** Better embeddings = better RAG recall; re-embedding the whole index is
  expensive and breaks reproducibility for older runs.
- **Leaning.** Default small local model in regime 1 (e.g. `nomic-embed-text` via
  Ollama); upgrade requires a side-by-side eval before swapping production index.
- **Affects.** `specs/services/rag_service.md` §10.2, `specs/data/vector_index.md`,
  `specs/serving/reasoning_llm_serving.md` §7.
- **Status.** `open`.

### A4 — Default for inferred vs explicit session typing

- **Question.** When the user types a first query without picking a session type, do we
  infer the type and confirm, or always require explicit selection?
- **Trade-off.** Inferring is the lower-friction UX; mis-inferring biases the entire
  session's posture (especially review-strictness on actionable types).
- **Leaning.** Infer + always confirm before committing the session type; once committed,
  do not change mid-session.
- **Affects.** `specs/agent/session_types.md` §7, `specs/interface/workspace_interface.md`
  §3.
- **Status.** `leaning infer-with-confirm`.

### A5 — Cross-session memory scope

- **Question.** What memory persists across sessions for one user (the "across all of my
  work" tier) vs stays session-local?
- **Trade-off.** Cross-session memory enables real recall ("you scored this variant last
  week"); it also creates a privacy / consent surface we currently dodge by keeping
  everything session-scoped.
- **Leaning.** Session-local in v1; explicit user-controlled cross-session memory in v2.
- **Affects.** `specs/agent/session_types.md` §7,
  `specs/agent/harness_and_context_engineering.md`,
  `specs/data/relational_schema.md`.
- **Status.** `open`.

### A6 — Whether to ship a CLI client alongside web/macOS

- **Question.** Does CellXP need a first-class CLI client for scripted / batch use, or
  does the OpenAPI + a sample script suffice?
- **Trade-off.** CLI is high-value for power users and reproducibility; it expands the
  client matrix the API contract must serve (web + macOS + CLI) and increases doc burden.
- **Leaning.** Sample-script-only for v1; reassess in M4+ when scripted use cases land.
- **Affects.** `specs/serving/frontend_deployment.md` §11,
  `documentation/reference/cli.md`.
- **Status.** `open`.

### A7 — Cross-region deployment in v1

- **Question.** Does CellXP need to run multi-region in v1 (regime 3)?
- **Trade-off.** Multi-region complicates SSE stickiness, checkpoint replication, and
  data-residency policy; single-region keeps the deployment model simple.
- **Leaning.** Single-region v1; multi-region is a deliberate later milestone.
- **Affects.** `specs/serving/agent_runtime_serving.md` §16,
  `specs/data/object_storage.md`.
- **Status.** `leaning single-region`.

### A8 — Difficulty rating on golden queries

- **Question.** Do golden queries carry a stable difficulty rating (easy/medium/hard) for
  stratified pass-rate reporting?
- **Trade-off.** Stratified reporting catches regressions hidden in averages; difficulty
  ratings are subjective and drift over time as the system improves.
- **Leaning.** Add an optional `difficulty` field; require it for new composed queries.
- **Affects.** `specs/evaluation/golden_query_sets.md` §12,
  `specs/evaluation/evaluation_plan.md`.
- **Status.** `open`.

### A9 — Specs-as-contracts machine-checking

- **Question.** Do we add a machine-checkable layer over numbered requirements
  (typed cross-references between `FR-*`/`NFR-*`/`PROV-*`/etc.) or keep them as plain
  text the way they are now?
- **Trade-off.** Machine-checking catches stale references and unenforced requirements;
  it adds a tooling layer that has to be maintained.
- **Leaning.** Keep plain-text in v1; introduce a linter (cross-link validity, ID-format
  enforcement) only if drift becomes a real cost.
- **Affects.** `ADR-0004`, `CONTRIBUTING.md`, every spec area.
- **Status.** `open`.

### A10 — When does an open question become an ADR

- **Question.** What's the trigger for promoting an open question to an ADR vs resolving
  in a spec edit?
- **Trade-off.** ADRs are heavyweight; spec edits are lightweight; meta-decisions
  (orchestration framework, repo layout, safety posture) deserve ADRs, mechanism-level
  decisions don't.
- **Leaning.** Promote to ADR when the decision is hard to reverse OR spans ≥ 2 spec
  areas; otherwise resolve in-spec.
- **Affects.** `documentation/adr/`, all spec areas.
- **Status.** `leaning above-criterion`.

### A12 — First-class citation-set artifact type

- **Question.** Should the next coordinated artifact-contract cycle add `citation_table` to the
  frozen `ArtifactType` enum, matching `rag_service.md` §5, or should citation sets remain report
  artifacts containing a resolvable citation map?
- **Trade-off.** A first-class type enables a dedicated renderer and makes the service spec literal;
  adding it now would violate the Wave 0 contract freeze, while `report` preserves citation
  resolution without changing shared contracts.
- **Leaning.** Add `citation_table` in the next coordinated contract cycle; X2 uses a non-actionable
  `report` artifact until then.
- **Affects.** `specs/services/rag_service.md` §5, `specs/interface/artifact_model.md` §4,
  `src/backend/cellxp/domain/enums.py`.
- **Status.** `open`.

### A13 — GWAS statistical-artifact taxonomy

- **Question.** Should the frozen artifact catalog add first-class `association_table`,
  `credible_set_table`, `coloc_table`, and `ld_matrix` types, or should GWAS continue using the
  generic `feature_table` plus `locus_plot`?
- **Trade-off.** First-class types give renderers precise contracts and match GWS-4, but expanding a
  frozen shared enum requires a coordinated contract cycle and increases pane taxonomy (R7).
- **Leaning.** Add the four types in the next coordinated artifact-contract cycle; use
  `feature_table` during X1 so the implementation does not mutate Wave 0 contracts.
- **Affects.** `specs/services/gwas_service.md` §5, `specs/interface/artifact_model.md` §4,
  `specs/interface/interactive_panes.md`, X1 locus-inspector rendering.
- **Status.** `open`.

## B. Per-spec open questions (index)

The authoritative wording for each item lives in the cited spec's own *Open questions*
section. This list exists so reviewers can find them all in one place.

### Agent
- `specs/agent/state_schema.md` §19 — state shape evolution and reducer compatibility.
- `specs/agent/graph_spec.md` §11 — graph topology trade-offs.
- `specs/agent/session_types.md` §7 — inferred vs explicit typing (see A4); cross-session
  memory (see A5); session-type change mid-life.
- `specs/agent/routing_policy.md` §11 — macro registry evolution.
- `specs/agent/tool_use_policy.md` §12 — model-selection edge cases.
- `specs/agent/harness_and_context_engineering.md` §5 — summarization defaults and
  retention.
- `specs/agent/evidence_integration.md` §12 — conflict-resolution heuristics.
- `specs/agent/human_review_policy.md` §10 — reviewer fatigue mitigations.
- Per-node files (`specs/agent/nodes/*.md`) — each carries its own list.
- Per-capability subgraph files (`specs/agent/capability-subgraphs/*.md`) — each carries
  its own list.
- `specs/agent/control-flow/replanning_and_budget.md` §6 — replanning thresholds.

### Services
- `specs/services/llm_service.md` §9 — context window, embedding ownership, per-role
  overrides (see A2).
- Other service specs — see their *Open questions* / *Failure modes* tails as applicable.

### Data
- `specs/data/provenance_model.md` §10 — hash algorithm, cache TTL, cross-run dedupe
  (see A1).
- `specs/data/object_storage.md` §9 — CAS scope (see A1), encryption-at-rest,
  multipart upload limits.

### Interface
- `specs/interface/streaming_protocol.md` §12 — reasoning granularity, persona defaults.
- `specs/interface/genome_browser.md` §14 — curated tracks per organism, base-level
  rendering cap, cross-organism comparison view.
- (`specs/interface/{api_contracts,artifact_model,interactive_panes,workspace_interface,chat_interface}.md`
  carry their tails; consult per-file.)

### Serving
- `specs/serving/reasoning_llm_serving.md` §13 — per-role defaults (see A2), built-in
  router, streaming reasoning edge cases, quantization defaults.
- `specs/serving/domain_model_serving.md` §14 — Triton/Ray-Serve default, per-tenant GPU
  budgeting, CAS cache scope (see A1), cross-tenant live-batching.
- `specs/serving/agent_runtime_serving.md` §16 — sticky-SSE policy, per-tenant queue
  placement, checkpoint compaction, multi-region (see A7).
- `specs/serving/frontend_deployment.md` §11 — Mol\* lock-in, CLI client (see A6),
  bundled local backend for macOS.

### Evaluation
- `specs/evaluation/biological_correctness_rubric.md` §10 — D7 clarification dimension;
  visualization correctness as a dimension; calibration cadence for fast-moving model
  upgrades.
- `specs/evaluation/safety_rubric.md` §11 — D1 near-miss sub-score; multi-turn safety
  scoring; hazard-set rotation on policy updates.
- `specs/evaluation/golden_query_sets.md` §12 — difficulty rating (see A8),
  partial-credit composed scoring, external-benchmark inclusion, hazard rotation policy.

### Planning
- `specs/planning/milestones.md` — M2 split, M3 inverse-design split, M5 macOS port
  fallback.
- `specs/planning/risks.md` — separate dual-use governance risk; public risks register;
  formal severity-likelihood matrix.

### Training
- `specs/training/post_training.md` §10 — SFT/DPO/RLVR sequencing, eval-set separation
  from training set (relates to R10 in `risks.md`).

### Biology
- `specs/biology/README.md` and per-capability files carry methodology-specific open
  questions; reviewers should read those alongside the service contract for the same
  capability.

## C. Resolution log

Items that left this index. (As decisions land, move them here with a one-line summary +
the ADR or spec edit that resolved them.)

- *(none yet — initial draft)*

## Review cadence

- **Per milestone gate.** Triage every open question; promote to leaning / decided where
  possible; archive resolved items to §C with a pointer.
- **On each ADR.** Cross-check that the ADR clears all items it should clear from this
  index.

## Related

`specs/planning/roadmap.md` · `specs/planning/milestones.md` ·
`specs/planning/risks.md` · `specs/planning/future-additions.md` ·
`documentation/adr/*` · every `specs/**/<file>.md` *Open questions* section linked above.
