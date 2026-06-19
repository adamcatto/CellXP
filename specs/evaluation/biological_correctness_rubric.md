# Biological Correctness Rubric

> Status: Draft v0.1. The scoring rubric used to judge whether a CellXP answer is
> **biologically correct**. It operationalizes D1 in `specs/product/success_metrics.md` and
> the per-capability acceptance bar in `specs/product/product_requirements.md`. Applied by
> evaluators against golden queries (`golden_query_sets.md`), against regression cases
> (`regression_tests.md`), and during release gating (`evaluation_plan.md`). Distinct from
> the safety rubric (`safety_rubric.md`) and the deterministic invariant tests (`tests/`).

## 1. What this rubric scores

A single agent **run** (one user turn → one final answer + artifacts + report + evidence
trail) on **one query**. The rubric scores the run as a whole; per-step inspection is allowed
to attribute failure but the score is the run's overall biological correctness.

Out of scope for this rubric:

- Latency, UI behavior, response style — covered by other rubrics / metrics
  (`success_metrics.md` D3/D4).
- Safety / refusal correctness — see `safety_rubric.md`.
- Deterministic invariants enforceable by unit tests (coordinate validation, schema
  conformance) — those are tests, not rubric scoring (`regression_tests.md`).

## 2. Scoring scale

Each dimension is scored on a 0–3 ordinal scale, applied independently:

| Score | Meaning |
|---|---|
| **3** | Correct and well-supported; a domain expert would accept it as is. |
| **2** | Correct on the main claim but with a recoverable shortfall (incomplete evidence, mild over-confidence, minor caveat missing). |
| **1** | Partially correct; the main claim is in the right direction but contains a substantive error, omission, or unjustified inference. |
| **0** | Wrong, hallucinated, biologically nonsensical, or framed at a confidence/recommendation level the evidence does not support. |

A run **passes** the biological-correctness rubric if and only if **all of the following**
hold:

- D1 (Claim correctness) ≥ 2
- D2 (Coordinate / organism correctness) ≥ 2
- D3 (Model / oracle appropriateness) ≥ 2
- D4 (Evidence grounding) ≥ 2
- D5 (Confidence calibration) ≥ 2
- D6 (Actionability framing) ≥ 2
- **No dimension scores 0.**

Any **0** is a blocking defect regardless of the other scores. The rationale: a single
biologically wrong claim makes the rest of the answer untrustworthy. A run with a single 0
is recorded as a release-blocking failure for the affected capability.

The run's **rubric score** is the *minimum* of its dimension scores (not the mean). Pass-rate
metrics in `success_metrics.md` D1 are computed on the pass/fail definition above, not on
score averages.

## 3. Dimensions

### D1 — Claim correctness

Is the principal claim of the answer biologically right, given the available evidence and the
state of public knowledge at the run's timestamp?

- **3** — The principal claim is correct, complete, and appropriately scoped (e.g. "this
  variant disrupts a GATA1 motif in erythroid cells with a predicted ATAC delta of −0.4σ").
- **2** — Correct claim with a minor omission (e.g. failed to mention a known tissue-context
  caveat).
- **1** — Direction correct, magnitude or scope wrong (e.g. "disrupts GATA1 binding" when
  the model output is borderline; or "loss of function" when the data supports only "reduced
  activity").
- **0** — Wrong sign, wrong target, wrong organism, hallucinated mechanism, or asserting
  knowledge the system did not actually produce.

### D2 — Coordinate / organism correctness

Did the run handle organism, assembly, contig, strand, and coordinate convention correctly?
This is the dimension that catches the largest class of high-severity bugs.

- **3** — All positioned claims use the right organism + assembly + strand; conventions
  (0-based half-open internal, native external) are labeled; circular contigs handled
  explicitly where applicable; any liftover is recorded.
- **2** — Correct overall but a minor convention label missing or a borderline circular case
  handled implicitly.
- **1** — One positioned element off by a convention (1-based vs 0-based mishandled in
  display); strand flipped on a one-off mention; uses GRCh37 when GRCh38 was clearly
  available.
- **0** — Wrong assembly silently used; wrong strand applied to a functional claim;
  cross-organism evidence applied to the wrong organism (e.g. human GWAS evidence applied to
  a mouse query); coordinate-convention mismatch that changes which base is affected.

> Any score of 0 here is a release blocker for the affected capability irrespective of
> other dimensions (`success_metrics.md` D1: coordinate-error rate target = 0).

### D3 — Model / oracle appropriateness

Did the agent pick a forward model / data source that is valid for the organism, assay,
tissue, sequence length, and variant class?

- **3** — Selected an oracle clearly within its declared support; surfaced the choice; would
  not have done better with a different oracle at comparable cost/latency.
- **2** — Reasonable choice; a marginally better alternative existed but the difference is
  small.
- **1** — Picked an oracle technically supported but a clearly better one was available
  (e.g. used motif scanning when AlphaGenome would have given a tissue-resolved delta).
- **0** — Picked an oracle **outside its declared support** (e.g. AlphaGenome assay heads
  on a bacterium, ESMFold on a complex requiring multimer prediction); silently let an
  unsupported oracle produce a result; ignored organism/assay metadata.

> Score 0 in D3 is a release blocker (`success_metrics.md` D1: organism-appropriate model
> selection target = 100%).

### D4 — Evidence grounding

Is every substantive claim linked to evidence (model output, database record, citation)
that the user can inspect and that genuinely supports the claim?

- **3** — Every substantive claim links to ≥1 `EvidenceItem` that a domain expert agrees
  supports it; citations resolve; provenance complete (`PROV-1/2`).
- **2** — All substantive claims linked, with one citation that supports the claim weakly or
  one minor claim with only inferential support.
- **1** — A substantive claim relies on evidence that does not clearly support it; a
  citation does not resolve; a model output is summarized in a way that overstates what the
  model reported.
- **0** — Hallucinated citation, fabricated evidence reference, or a substantive claim with
  no supporting evidence at all.

### D5 — Confidence calibration

Does the answer represent its uncertainty appropriately? Are predicted-vs-curated and
high-confidence-vs-borderline distinctions visible?

- **3** — Confidence indicators are present per claim, calibrated to the evidence type
  (model-derived confidence, source quality, agreement across evidence); borderline / low
  -support claims are clearly flagged.
- **2** — Confidence is generally appropriate but a single claim is somewhat over- or
  under-stated.
- **1** — Multiple claims overstate confidence; conflicting evidence is silently averaged
  or hidden; "the variant is pathogenic" framed without the qualifying confidence band.
- **0** — Strong claims made on weak / borderline / contradictory evidence; "definitely",
  "always", or recommendation-grade framing on speculative output.

### D6 — Actionability framing

If the run produced actionable artifacts (CRISPR guides, origami designs, protein designs),
were they framed as **candidates pending review** rather than as recommendations to act?
Did the run respect the review gate (`ADR-0005`, `human_review_policy.md`)?

- **3** — Actionable outputs labeled CANDIDATE with rationale, risks, and limitations;
  review gate emitted; no recommendation framing prior to approval.
- **2** — Labeled correctly but rationale/risks are thin.
- **1** — Borderline framing (e.g. "use this guide" instead of "candidate guide pending
  review") but the gate still emitted.
- **0** — Recommendation framing on an actionable output that bypassed or preempted the
  review gate.

> Score 0 in D6 is a release blocker (`success_metrics.md` D5: review-gate enforcement
> target = 100%). It also fails `safety_rubric.md`.

## 4. Per-capability overlays

Dimension definitions are global; the worked examples below show how each lands per
capability so evaluators score consistently. The overlay is illustrative, not exhaustive —
the catalog of supported workloads is `specs/biology/*.md`.

### Variant interpretation

- D2: ref-allele validation against the named assembly is a hard pass/fail.
- D3: AlphaGenome assay heads only for supported organisms; non-mammalian → Evo 2-class.
- D4: every reported effect (track delta, motif disruption, splice impact) links to its
  model evidence; literature claims to a `RAG` evidence item.
- D5: confidence on each effect (per-assay or per-window), not a single aggregate.

### CRISPR design

- D2: assembly + strand + Cas/PAM/edit-spec all correct; off-target search on the **named
  organism's** reference, never the human default.
- D3: editor compatibility checked (base/prime editor capability matches the edit_spec).
- D5: on-target / off-target / outcome confidence reported separately; "no feasible
  candidates" distinguished from "tool failure".
- D6: every `guide_table` / `off_target_table` actionable and review-gated.

### Structure prediction

- D2: chain map + residue numbering correct; ligand standardization recorded.
- D3: ESMFold for fast single-sequence; Boltz-2-class for multimer / ligand-aware /
  nucleic-acid-aware.
- D5: per-residue confidence (pLDDT-like) exposed; "low-confidence structure" is a valid
  result with flags, not a failure.

### GWAS / QTL

- D2: assembly + liftover recorded; population / panel matched.
- D3: human-only datasets not used for non-human evidence.
- D4: every association cites source database + release + study accession/PMID.
- D5: PIPs / coloc H4 / p-values exposed; "no records" distinguished from "resource lacks
  coverage" distinguished from "query failed".

### Origami

- D2: geometry units consistent; scaffold identity + sequence hash recorded.
- D3: PERDIX-class for wireframe, DAEDALUS/TALOS/ATHENA-class for 3D mesh; tool selection
  recorded.
- D6: every buildable design + staple table + cadnano export actionable and review-gated;
  critical QC checks pass before "buildable" framing.

### RAG / literature

- D4: every claim citation resolves to an accessible source (or marks the limitation if
  paywalled); no fabricated citations.
- D5: confidence reflects source quality, recency, directness, and agreement.

### Annotation / discovery

- D2: organism-appropriate annotation pipeline (eukaryotic vs prokaryotic gene finding,
  ncRNA, BGCs); circular bacterial assemblies handled.
- D3: choice of pipeline (Prokka vs MAKER vs Funannotate vs antiSMASH) matches input.

### Visualization

- This rubric does not score visualizations independently; visualization correctness reduces
  to whether the underlying typed payload is correct (D1) and the coordinate metadata is
  preserved (D2). Visualization-specific UX is scored by other measures.

## 5. Who scores, and how

- **Tier-1 scoring (default):** domain-knowledgeable evaluators (internal or contracted)
  apply the rubric to golden-query outputs. Each query has at least one scorer; high-stakes
  capabilities (CRISPR, origami, design) have two with disagreement adjudicated by a third.
- **Tier-2 scoring (LLM-assisted, optional):** an evaluation LLM applies the rubric against
  the run trace + expected outcome to suggest scores; tier-1 confirms or overrides. LLM
  scores are NEVER load-bearing for release gating; they are triage to surface candidates
  for human review.
- **Disagreement:** for tier-1 disagreements of ≥2 score points, a third evaluator
  adjudicates and the case is captured in a calibration log so future scoring tightens.
- **Calibration cadence:** before each release, scorers calibrate on a small shared subset
  (≥ 20 queries spanning capabilities) to keep inter-rater agreement above 0.7 Cohen's κ.

## 6. Evidence the scorer needs

Every scored run MUST be inspectable via the run inspector (`interactive_panes.md` §3.5).
Scoring requires access to:

- the final answer (message + report) and any artifacts,
- the subtask DAG and per-step inputs/outputs/tool versions,
- every `EvidenceItem` and its provenance,
- the `citation_map` for the report,
- the run's audit log entries (review decisions, refusals, any side effects).

A run that does not provide complete inspection is automatically scored 0 on D4 regardless of
content — the user cannot verify what cannot be inspected.

## 7. Recording results

Per-query scoring records, in `evals/results/<run-id>.json`:

```json
{
  "query_id": "var-001-brca1-clinvar-rs28897696",
  "run_id": "run_01J...",
  "scorer_id": "...",
  "scored_at": "...",
  "dimensions": {
    "D1": 3, "D2": 3, "D3": 3, "D4": 2, "D5": 3, "D6": 3
  },
  "rubric_score": 2,
  "passed": true,
  "notes": "Mild over-claim on tissue specificity; rest is correct and well-evidenced.",
  "blocking_defects": []
}
```

Per-release aggregates roll up to D1 metrics in `success_metrics.md` and are surfaced in the
release readiness report (`evaluation_plan.md` §3).

## 8. Calibration examples

Each golden-query category SHOULD ship with at least one **calibration example** showing a
worked rubric scoring with rationale per dimension. Examples live in
`evals/calibration/<capability>/<example_id>.md`. The biology team owns the calibration set;
it expands as edge cases surface during scoring.

## 9. Requirements

- **BCR-1** Every release MUST score the full golden-query set against this rubric; the v1
  release gate requires ≥ 75% pass rate overall and ≥ 70% per capability
  (`success_metrics.md` D1).
- **BCR-2** A single 0 on any dimension MUST block release for the affected capability until
  remediated; a 0 on D2 (coordinates) or D3 (oracle appropriateness) or D6 (review gate)
  blocks release for the whole product.
- **BCR-3** Scorers MUST have access to the full run inspector; runs that cannot be fully
  inspected score 0 on D4.
- **BCR-4** Tier-2 (LLM-assisted) scores MUST NOT be the sole basis for release gating;
  tier-1 confirmation is required.
- **BCR-5** Inter-rater agreement (Cohen's κ) MUST be tracked across releases; sustained
  agreement < 0.7 triggers a calibration review.
- **BCR-6** Per-capability overlays MUST be kept current with the capability specs
  (`specs/biology/*`); a new capability MUST land with its overlay updates in the same
  release.

## 10. Open questions

- Whether to add a D7 dimension for "appropriateness of clarification" (did the agent ask
  the right clarifying questions before producing an answer?) or fold it into D5.
- Whether to score visualization correctness as a separate D7 once the visualization
  service has more sophisticated outputs than direct projection of typed payloads.
- Calibration cadence for fast-moving model upgrades (e.g. an AlphaGenome revision): is the
  20-query subset enough, or do we need a stratified calibration?

## 11. Related

`specs/evaluation/evaluation_plan.md` · `specs/evaluation/golden_query_sets.md` ·
`specs/evaluation/regression_tests.md` · `specs/evaluation/safety_rubric.md` ·
`specs/product/success_metrics.md` D1 · `specs/biology/*.md` ·
`documentation/explanation/evidence_and_confidence.md` ·
`specs/agent/human_review_policy.md` · `ADR-0005`.
