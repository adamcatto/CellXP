# CRISPR Service

> Status: Draft v0.1. Logical service contract for guide design, base/prime editing, and
> off-target analysis. Impl: `src/backend/cellxp/services/crispr/`. Methodology:
> `specs/biology/crispr_design.md`, `specs/biology/inverse_edit_design.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §10, §11. Actionable outputs are
> review-gated.

## 1. Purpose

Design and score genome-editing candidates while preserving strict provenance, organism-specific
coordinate handling, and human review. The service returns candidate artifacts, not recommendations;
recommendation framing happens only after the human-review gate.

## 2. Operations

```python
class CrisprService(Service):
    def design_guides(self, request: CrisprRequest) -> ServiceResult[CrisprResult]: ...
    def enumerate_off_targets(self, request: OffTargetRequest) -> ServiceResult[OffTargetResult]: ...
    def score_on_target(self, request: GuideScoringRequest) -> ServiceResult[GuideScoringResult]: ...
    def predict_edit_outcomes(self, request: EditOutcomeRequest) -> ServiceResult[EditOutcomeResult]: ...
```

`design_guides` composes PAM enumeration, on-target scoring, off-target enumeration, edit-outcome
prediction, ranking, and artifact creation.

## 3. Inputs

Inputs MUST include organism, assembly, target coordinates, edit type, and any explicit Cas/PAM or
editor choice. Base/prime-edit requests require an `edit_spec`; missing or ambiguous edit specs
trigger a clarification before this service runs.

Coordinate handling MUST support both strands and circular microbial genomes. Off-target analysis
uses the named organism's reference genome, never a default human genome.

## 4. Execution

Light operations: target resolution, sequence extraction, PAM scanning, ranking. Heavy operations:
genome-wide off-target enumeration and edit-outcome prediction; these SHOULD run as async jobs for
large genomes or batches.

The service MUST stream progress through `step.started`, `activity.update`, and `step.finished`
events because off-target scans can be long-running.

The implemented `http` adapter delegates typed operations to a separately deployed worker expected
to pin Rule Set 2, CFD, Cas-OFFinder, and outcome-model revisions. It validates worker responses and
uses bounded retries for transient failures. The `deterministic` offline adapter provides only
sequence-QC scores and empty search/outcome results; it never labels its heuristic as Rule Set 2 or
claims genome-wide completeness.

## 5. Outputs & Artifacts

| Output | Artifact type | Actionable | Storage |
|---|---|---:|---|
| ranked guides | `guide_table` | yes | inline top rows + full object |
| off-target profile | `off_target_table`, `genome_track` | yes | object storage |
| edit context | `sequence_editor` | yes | inline context + object if large |
| scoring rationale | `score_table` | yes | inline summary |

All actionable artifacts set `ArtifactRef.actionable=true` and create `ReviewItem`s before they are
presented as recommendations.

## 6. Provenance & Confidence

Provenance records Cas/editor, PAM, genome assembly, reference sequence hash, scoring models,
off-target mismatch thresholds, and tool versions. Confidence combines on-target model reliability,
off-target search completeness, edit-window fit, organism/Cas applicability, and outcome model
support.

## 7. Safety & Review

This service never bypasses `specs/agent/human_review_policy.md`. Outputs are "candidate guides" or
"candidate edits" until approved. `risk=restrict` forces review even for outputs that might otherwise
be presented as exploratory.

## 8. Failure Modes

- no compatible PAM: return no-candidate result and suggest alternate Cas/PAM choices;
- repetitive target: return candidates with elevated off-target risk;
- off-target index unavailable for organism: recoverable error, no recommendation framing;
- edit_spec impossible for chosen editor: validation error with alternatives;
- genome sequence unavailable: hard validation error.

## 9. Requirements

- **CRS-1** Every physical-intervention output MUST be marked actionable and review-gated.
- **CRS-2** Off-target analysis MUST run against the requested organism/assembly.
- **CRS-3** Guide rows MUST include sequence, PAM, strand, cut/edit coordinate, on-target score,
  specificity/off-target summary, confidence, and provenance.
- **CRS-4** Large guide/off-target tables MUST use object storage.
- **CRS-5** The service MUST clearly distinguish "no feasible candidates" from tool failure.

## 10. Related

`specs/biology/crispr_design.md` · `specs/biology/inverse_edit_design.md` ·
`specs/agent/human_review_policy.md` · `specs/data/audit_log.md` ·
`specs/interface/artifact_model.md`.

## 11. Verification

Transport retry, schema validation, offline determinism, and environment selection are T1 tests in
`tests/unit/test_crispr_production_backends.py`. Run
`python -m pytest tests/unit/test_crispr_production_backends.py -q`. The opt-in T2 smoke requires a
live worker: `CELLXP_RUN_LIVE_CRISPR=1 CRISPR_BACKEND=http CRISPR_SERVICE_URL=<url> python -m pytest
-m live tests/integration/test_live_production_adapters.py -q`.
