# Golden Query Sets

> Status: Draft v0.1. The **curated query catalogs** CellXP is scored against during
> evaluation and release gating. Consumed by `evaluation_plan.md` and `regression_tests.md`;
> scored against `biological_correctness_rubric.md` and `safety_rubric.md`; thresholds in
> `specs/product/success_metrics.md`. Implemented under `evals/golden_queries/`.

## 1. Purpose

A **golden query** is a canonical user query paired with an **expected-shape outcome** that
an evaluator (human or rubric-LLM) can score against. Golden sets exist so that:

- **Releases gate on real biology**, not on synthetic micro-benchmarks
  (`evaluation_plan.md` §3, `success_metrics.md` D1).
- **Behavior regressions are visible**: a query that passed in v0.5 and fails in v0.6 is a
  bug, not a fluctuation.
- **The capability surface is honestly covered**: every supported capability, every
  supported organism class, every actionable artifact type, every refusal class has at
  least minimal representation.
- **Safety is exercised structurally**: the safety rubric runs against queries designed to
  probe gates, classification, and refusal correctness, not against ad-hoc red-team text.

What golden queries are NOT:

- Unit tests. Deterministic invariants live in `tests/` (`testing_strategy.md`).
- Benchmarks against published leaderboards. We may consume those externally; the golden
  sets here are the *product's* scoring substrate.
- A static frozen list. The sets evolve under a defined policy (§8).

## 2. Catalog structure

```
evals/golden_queries/
├── biology/                          # public, biological-correctness focus
│   ├── variant_interpretation/
│   ├── crispr_design/
│   ├── structure_prediction/
│   ├── gwas_qtl/
│   ├── binding/
│   ├── annotation/
│   ├── rag_literature/
│   ├── origami/
│   ├── visualization/
│   └── composed/                     # multi-capability compositions
├── safety/                           # mixed visibility (§4)
│   ├── adjacent_legitimate/
│   ├── actionable_gate/
│   ├── gate_evasion/
│   ├── early_classification/
│   ├── leakage/
│   ├── honesty/
│   ├── privacy_egress/
│   └── hazard/                       # private; access-controlled (§4.2)
└── calibration/                      # worked examples per capability (BCR §8, SFR §6)
```

- One JSONL file per leaf directory; each line is one query.
- Calibration examples carry full rubric-by-rubric scoring with rationale, so new scorers
  can ramp.
- The `hazard/` directory is **not in the public repo**; it lives in a private store with
  access logged.

## 3. Query schema

Every golden query is a typed record:

```python
class GoldenQuery(BaseModel):
    id: str                                   # stable, kebab-case, capability-prefixed
    capability: str                           # primary capability, or "composed"
    session_type: SessionType | None = None   # if the query is session-typed
    organism: str | None = None
    assembly: str | None = None
    persona: str | None = None
    inputs: list[RawInput] = []               # files / variants / sequences / entities
    message: str | None = None                # the user's natural-language turn
    overrides: dict[str, Any] = {}            # explicit RunOverrides for the test
    expected: ExpectedOutcome                 # see §3.1
    references: list[str] = []                # FR-*/NFR-*/PROV-*/ART-* IDs covered
    sources: list[str] = []                   # provenance of the query itself (§7)
    risk_class: RiskClass | None = None       # safety queries: expected risk class
    tags: list[str] = []                      # circular_bacterial, low_confidence, ...
    added_at: str                             # UTC ISO-8601
    last_reviewed_at: str
```

### 3.1 Expected outcome

An expected outcome is *shape-typed*, not value-typed, because the agent's responses are
nondeterministic. The shape lists what MUST and MUST NOT appear in the run:

```python
class ExpectedOutcome(BaseModel):
    must_contain: list[ExpectedClaim] = []    # claims/effects the answer must include
    must_not_contain: list[ExpectedClaim] = []
    required_artifacts: list[RequiredArtifact] = []
    required_evidence_sources: list[str] = [] # e.g. "alphagenome", "pubmed", "gwas_catalog"
    required_models: list[ModelRequirement] = []  # organism-appropriate-model checks
    must_emit_review_gate: bool = False
    must_classify_risk_as: RiskClass | None = None
    must_refuse: bool = False
    must_clarify: bool = False                # query is intentionally ambiguous
    coordinate_frame: CoordinateFrame | None = None  # for positioned queries
    rubric_dimensions: list[str]              # which dimensions this query exercises
    notes: str | None = None
```

Rubric scoring (`biological_correctness_rubric.md`, `safety_rubric.md`) interprets these
shapes; deterministic post-conditions (e.g. "every claim has linked evidence") are checked
by the evaluation runner before human scoring.

## 4. Biology sets

### 4.1 Coverage requirements

The biology sets MUST collectively exercise:

- Every **capability** in `specs/agent/capability-subgraphs/*.md`.
- Every **supported organism class** in `specs/biology/supported_species.md` (at minimum:
  human, mouse, model microbe, plasmid, exemplar prokaryote, exemplar non-model eukaryote).
- Every **supported assay/tissue head** in `specs/biology/supported_assays.md` for at
  least one query each.
- Every **actionable artifact type** in `specs/interface/artifact_model.md` §4.
- **Edge cases** with explicit tags: circular bacterial assemblies, origin-crossing
  intervals, ambiguous gene symbols across species, low-confidence model outputs,
  conflicting evidence, paywalled/missing-full-text RAG sources, ref-allele mismatches that
  the agent must reject.
- **Compositions**: at least one multi-capability query per supported composition pattern
  in `documentation/explanation/task_patterns.md` (variant→GRN, variant→metabolism, strain
  engineering, inverse edit design, etc.).

### 4.2 Minimum size at v1

- ≥ 200 queries total in `biology/`, distributed so no capability has < 15 queries and no
  organism class has < 10 queries.
- ≥ 30 of those tagged as edge cases (circular, ambiguous, conflicting, unsupported).
- ≥ 25 composed queries.

These are floors, not targets. The biology team owns growth.

**Public-catalog checkpoint (2026-06-23).** The release-facing variant-effect, GWAS, structure,
CRISPR, inverse-design, binding, RAG, visualization, and reference catalogs each contain at least 15
sourced cases; the composed catalog contains 25. Across those catalogs, the human, mouse,
model-microbe, exemplar-prokaryote, plasmid, and non-model-eukaryote buckets each have at least 10
cases, and at least 30 records carry an explicit edge-condition tag. The whole public biology
catalog contains exactly 200 reviewed records: 199 release-facing M1–M3 cases plus the pre-existing
single annotation seed. It therefore satisfies the v1 size floor without adding M4 annotation or
strain-optimization scope. This count checkpoint is not an M1–M3 pass rate and is not private
safety-set evidence; release gates still require scored live results.

## 5. Safety sets

### 5.1 Coverage requirements (per `safety_rubric.md` §4)

The safety sets MUST collectively exercise:

- **Hazard refusal** — sized for statistical reliability of the 100% recall target; private.
- **Adjacent legitimate research** — explicitly proximal to flagged topics; tests D2
  over-refusal.
- **Actionable-output gate enforcement** — per actionable artifact type (CRISPR, origami,
  protein design); tests D3.
- **Gate-evasion attempts** — adversarial prompt patterns (role-play, scope splitting,
  "just curious", multi-turn priming); tests D3 + D6.
- **Early-classification** — queries crafted so any capability call would happen before
  classification if the graph drifted; tests D4.
- **Leakage** — uploads with embedded secrets, queries probing for raw prompts / object
  keys / cross-session resources; tests D5.
- **Honesty** — queries that elicit refusal/approval framing the system might soften
  deceptively; tests D6.
- **Privacy egress** — sensitive-class sequence inputs with a hosted provider configured;
  tests the consent gate.

### 5.2 Access to the hazard set

- The hazard subdirectory (`safety/hazard/`) is **not in the public repository**. It lives
  in a private store with per-access audit logging.
- Only authorized safety reviewers may pull or score the hazard set.
- A CI job that requires the hazard set MUST run inside an isolated environment with the
  appropriate credentials; results MUST NOT echo hazard query text to public logs.
- Public mirroring of the catalog includes a manifest entry per hazard query (ID + scoring
  result) but not the query text.

### 5.3 Minimum size at v1

- ≥ 50 hazard queries (private), distributed across the policy categories in
  `safety_model.md`.
- ≥ 50 adjacent-legitimate queries (public).
- ≥ 40 actionable-gate queries spanning every actionable artifact type.
- ≥ 20 gate-evasion queries.
- ≥ 20 leakage queries.
- ≥ 20 honesty queries.

The public repository contains no placeholder hazard prompts, policy-category labels, or scores.
`evals/golden_queries/safety/private_hazard_manifest.schema.json` is only an integration hook for
opaque authorized result IDs and references. Entries exist only after real private execution and
review; missing private results remain missing release evidence.

## 6. Composed sets

Composed queries are the highest-signal evaluation surface because they exercise the
supervisor's planning and routing, not just one capability. Patterns to cover (each ≥ 3
queries):

- variant → regulatory effect → affected gene → fold protein candidate → visualize
- variant → GWAS → fine-map → coloc → report
- strain optimization: target phenotype → GRN/metabolic → propose edits → off-target check
- inverse edit design: desired effect → propose edits → score with forward oracle →
  off-target penalty → iterate
- annotation: upload prokaryotic FASTA → annotate → BGC search → propose edits
- RAG-heavy: literature question → multi-source synthesis → cited report

Each composed query references the capability-subgraph contracts it exercises in
`references`.

## 7. Sourcing queries

Queries are sourced from:

1. **User stories** in `specs/product/user_stories.md`, where seed entries are marked
   *golden seed*. Every golden-seed story produces at least one query.
2. **Capability specs** (`specs/biology/*.md`) — for each "Supported workloads" entry, at
   least one query.
3. **Edge-case derivation** — `documentation/explanation/coordinate_systems.md` and
   capability open-questions sections inform the edge-case tag set.
4. **Real failures** — when a capability fails in a way the test suite missed, the
   reproduction query is added (anonymized as needed) to the regression subset.
5. **External validation sets** (where licensing permits) — public benchmarks for variant
   effect / structure / GWAS may be incorporated with attribution; their IDs map to a
   `sources: ["benchmark:<name>"]` entry.
6. **Red-team queries** — for the hazard subdirectory only, generated during periodic
   safety reviews.

Each query record's `sources` field MUST identify its provenance; an unsourced query is a
review reject.

## 8. Lifecycle & evolution

### 8.1 Adding a query

- Open a PR adding the JSONL line and any required calibration example.
- The PR MUST: (a) reference the FR/NFR/PROV/ART IDs the query exercises; (b) include the
  expected outcome shape; (c) pass linting (schema + required-fields).
- Domain review for biology sets; safety review for safety sets; the **hazard set** is
  added in the private store with review by ≥2 authorized reviewers.

### 8.2 Modifying a query

- Substantive edits to an existing query change its scoring history. Either:
  - keep the ID and bump a `revision` field (acceptable for clarifications that don't
    change the expected outcome), OR
  - retire the old ID and add a new one (required when the expected outcome changes).
- The CHANGELOG records the change so per-release metric movements can be attributed.

### 8.3 Retiring a query

- A query is retired when (a) the capability it tests is deprecated, (b) the expected
  outcome no longer reflects current science, or (c) it has been replaced by a better
  query. Retired queries are kept in the repository under `archive/` for historical
  reference but do not count toward release gating.

### 8.4 Refresh cadence

- The biology team reviews ≥ 10% of biology queries per quarter, prioritizing queries
  whose `last_reviewed_at` is oldest. Queries unreviewed for > 12 months are flagged.
- The safety team reviews ≥ 25% of safety queries per quarter (higher cadence because the
  policy moves faster).
- Major dependency upgrades (new model revision, new reference release) trigger a partial
  refresh of affected queries; the eval report flags such cases.

## 9. Stability against model nondeterminism

Because the reasoning LLM and several domain models are nondeterministic, the expected
outcome model is intentionally **shape-based**:

- "Must contain a claim about ATAC delta in erythroid context" — not "must contain the
  exact sentence …".
- "Must produce at least one `guide_table` artifact with ≥ 1 candidate" — not "must
  produce exactly 5 candidates".
- "Must NOT use AlphaGenome on a bacterial query" — invariant regardless of model
  revision.

The rubric (`biological_correctness_rubric.md`) is the value judge; the expected-outcome
shape is the *pre-condition gate* that catches obviously-off runs before scoring.

## 10. Running the sets

The runner lives at `evals/run_evals.py`. Invocation:

```
python evals/run_evals.py --set biology --capability variant_interpretation --concurrency 4
python evals/run_evals.py --set safety --include-hazard       # requires auth
python evals/run_evals.py --set all --release-gate            # full nightly / pre-release
```

The runner:

1. Loads queries from the requested set(s).
2. Dispatches each as a real run against the agent runtime (`agent_runtime_serving.md`).
3. Collects the run trace, artifacts, evidence, and audit log.
4. Applies deterministic post-conditions from the expected outcome.
5. Writes results to `evals/results/`; if `--score auto` is given, asks the eval LLM for
   tier-2 triage scores (subject to rubric §6 constraints).
6. Aggregates pass-rates and writes a release-readiness report
   (`evaluation_plan.md` §3).

LangSmith tracing is opt-in via `LANGSMITH_*` env (`.agents/guidelines/langsmith.md`).

## 11. Requirements

- **GQS-1** Every release MUST run the full public golden set (biology + non-hazard safety)
  and the private hazard set; results MUST be archived per
  `evaluation_plan.md`.
- **GQS-2** Coverage minimums (§4.2, §5.3, §6) MUST be met for the v1 release; subsequent
  releases MUST NOT regress coverage.
- **GQS-3** Every query MUST carry a sourced provenance entry; unsourced queries are
  rejected at review.
- **GQS-4** Modifying the expected outcome of a query MUST retire the old ID and add a new
  one; revisions that change the scoring substrate MUST be recorded in CHANGELOG.
- **GQS-5** The hazard subdirectory MUST NOT be present in the public repository and access
  MUST be audited.
- **GQS-6** Tier-1 scoring against the rubrics is required for release gating; tier-2
  (LLM-assisted) is supplementary only (`BCR-4`, `SFR-6`).
- **GQS-7** Calibration examples MUST exist for every capability and every safety category;
  missing calibration blocks the addition of new queries in that area.
- **GQS-8** Public queries MUST NOT contain personal genomic data, PHI, or any payload
  flagged FC-1 (`product_requirements.md`).

## 12. Open questions

- Whether to attach a stable **difficulty rating** per query to allow stratified pass-rate
  reporting (easy / medium / hard) or rely on per-capability grouping.
- Whether composed-query expected outcomes need a partial-credit model (some sub-goals
  achieved) instead of strict shape matching.
- Cadence and process for incorporating external benchmark datasets (license handling,
  version pinning).
- For the hazard set: rotation policy as the safety policy evolves — when does a query
  become "answered" by a policy update?

## 13. Related

`specs/evaluation/evaluation_plan.md` · `specs/evaluation/regression_tests.md` ·
`specs/evaluation/biological_correctness_rubric.md` · `specs/evaluation/safety_rubric.md` ·
`specs/evaluation/testing_strategy.md` · `specs/product/user_stories.md` ·
`specs/product/success_metrics.md` · `documentation/explanation/safety_model.md` ·
`documentation/explanation/task_patterns.md` · `.agents/guidelines/langsmith.md`.
