# Evidence Integration

> Status: Draft v0.1. Defines how the agent collects, normalizes, reconciles, and weights evidence
> from many tools into a coherent, cited, confidence-qualified answer. Consumes the `EvidenceItem`/
> `Confidence`/`Provenance` shapes (`state_schema.md` §9) and the semantics in
> `documentation/explanation/evidence_and_confidence.md`. Implementation:
> `agent/nodes/evidence_integrator.py`, `agent/nodes/critic.py`, `domain/evidence.py`.

## 1. Purpose

Turn the raw `evidence` accumulated by subgraphs into: (a) a de-duplicated, reconciled evidence set,
(b) per-claim and overall **confidence**, and (c) a **citation map** the report writer uses so every
substantive claim is traceable (`FR-22..24`).

## 2. Where it runs

`evidence_integrator` runs after capability subgraphs and before `critic`/`report_generator`
(`graph_spec.md`). It is idempotent and re-runnable as more evidence arrives (e.g. after a replanning
loop). It only **reduces/annotates** evidence; it does not call domain models.

## 3. Inputs & outputs

- **In:** `evidence` (append-only list from all subgraphs), `artifacts`, `entities`, `subtasks`.
- **Out:** normalized/merged `evidence`, a `citation_map` and `confidence_summary` for the `Report`,
  and `critic`-consumable flags (gaps, conflicts).

## 4. The evidence record (recap)

Each `EvidenceItem` carries `source`, `source_kind` (`model|database|literature|computation`),
`claim`, structured `value`, `confidence`, `provenance`, and links to the `subtask`/`step` that
produced it (`state_schema.md` §9). Integration operates over these.

## 5. Pipeline

1. **Normalize** — coerce heterogeneous tool outputs into `EvidenceItem`s with consistent units and
   claim phrasing; attach provenance (tool+version+params+inputs/citations).
2. **De-duplicate** — merge items asserting the same claim from the same source/version; keep one with
   combined provenance.
3. **Group by claim** — cluster items that bear on the same proposition (e.g. "variant X reduces
   expression of gene Y in tissue Z").
4. **Reconcile** — within a claim group, detect agreement/conflict across independent sources (§6).
5. **Weight & score** — assign per-claim confidence from source reliability + agreement + individual
   confidences (§7).
6. **Build citation map** — assign stable citation markers → `evidence_id`(s) for the report
   (`state_schema.md` §11).
7. **Flag gaps/conflicts** — surface unsupported-but-needed claims and unresolved conflicts to
   `critic` and into `Report.limitations`.

## 6. Reconciliation (agreement vs conflict)

- **Corroboration** — independent sources (e.g. AlphaGenome prediction + an eQTL record + a paper)
  agreeing raises confidence; record the corroborating set.
- **Conflict** — disagreeing sources are NOT silently averaged. The integrator:
  - keeps both, marks the claim `contested`,
  - prefers higher-reliability/more-direct evidence (measurement > prediction; primary > secondary),
    but
  - never hides the dissent — it appears in `limitations` and the report notes the disagreement.
- **Independence matters** — two tools sharing the same underlying model/data are not independent
  corroboration; provenance is used to judge independence.

## 7. Confidence model

Per-claim confidence combines:
- **Source reliability** by `source_kind` and tool (experimental measurement > validated DB record >
  model prediction > heuristic);
- **Directness** (does the evidence speak to the claim directly or by proxy);
- **Agreement** across independent sources;
- **Native confidence** of each item (calibrated `score` or qualitative `band`).

Output is a `Confidence{band, score?, basis}` per claim and a run-level `confidence_summary`.
Semantics, bands, and calibration guidance: `evidence_and_confidence.md`. **"Insufficient evidence"
is a valid, preferred outcome** over confident fabrication (`mission.md` §5).

## 8. Composed/systems-level: uncertainty propagation

For chained tasks (`task_patterns.md` §2–§6), confidence MUST compound, not reset:
- a chain's confidence is bounded by its **weakest load-bearing step**;
- the integrator records the limiting step and reflects it in `confidence_summary`;
- per-stage intermediate evidence remains individually addressable so users can audit where
  uncertainty enters.

## 9. Provenance completeness (gate on quality)

Before report generation, the integrator checks that every claim destined for the answer has linked
evidence with complete provenance. Claims failing this are either dropped, demoted to clearly-labeled
speculation, or flagged for `critic`. Target: ≥95% provenance completeness
(`success_metrics.md` D2).

## 10. Critic interaction

`critic` consumes the integrated set + flags to self-check the draft: unsupported claims, ignored
conflicts, overconfident language, missing limitations. It may request replanning
(`routing_policy.md` §9) if a gap is fillable within budget, or annotate the report's limitations if
not.

## 11. Report hand-off

`report_generator` receives: reconciled `evidence`, `citation_map`, `confidence_summary`,
`limitations`, and `artifact_ids`. Every substantive sentence in `Report.markdown` MUST reference a
citation marker resolving to evidence; uncited assertions are not permitted for substantive claims.

## 12. Open questions

- Exact reliability ordering/weights per `source_kind` and per tool (config vs learned).
- Quantitative scheme for combining bands+scores into a single per-claim confidence.
- How to represent partial/where-it-breaks confidence visually (hand-off to artifact/UI specs).

## 13. Related specs

`state_schema.md` · `graph_spec.md` · `human_review_policy.md` ·
`documentation/explanation/evidence_and_confidence.md` · `specs/data/provenance_model.md` ·
`success_metrics.md` · `task_patterns.md`.
