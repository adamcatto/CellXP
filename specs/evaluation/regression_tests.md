# Regression Tests

> Status: Draft v0.1. **Regression** here means automated re-verification that shipped behavior and
> invariants do not slip. The full tier model (unit → browser → evals), CI triggers, and `TST-*`
> requirements live in `testing_strategy.md`. This doc names **what must never regress** and where
> those checks live.

## 1. P0 — release blockers (zero tolerance)

| Invariant | Requirement | Primary tests |
|---|---|---|
| Coordinate/assembly/strand | `NFR-3` | `tests/unit/test_coordinate_validation.py`, `test_variant_normalization.py` |
| Safety refusal / allow | `FR-33..35` | `tests/unit/test_risk_classifier.py`, T6 safety rubric |
| Human-review gate | `FR-25/26` | `tests/integration/test_crispr_gate.py` (+ per-capability analogs) |
| No secrets in logs/audit | `NFR-7`, `AL-3` | unit lint on audit writers |

## 2. P1 — contract and trust regressions

| Area | Checks |
|---|---|
| API / OpenAPI | T3 contract tests; TS client generation (`API-9`) |
| Streaming / resume | T4 e2e SSE ordering (`API-4`, `API-5`) |
| Provenance completeness | T6 provenance rubric; `specs/data/provenance_model.md` regression cases |
| Organism-appropriate models | T6 eval audit; `tool_use_policy.md` §4 |

## 3. P2 — quality regressions (eval thresholds)

Golden-query accuracy, hallucination rate, per-capability pass rates — thresholds in
`success_metrics.md`, enforced by T6 nightly (`TST-8`). Failures block **release**, not every PR.

## 4. Adding a regression case

1. Classify tier (T1–T6) per `testing_strategy.md`.
2. Add fixture + test or golden query; reference the `FR-*`/`NFR-*`/`API-*` ID in a comment.
3. If P0, test MUST run in default PR CI (`TST-1`/`TST-2`).

## 5. Related

`testing_strategy.md` · `evaluation_plan.md` · `golden_query_sets.md` ·
`.agents/guidelines/testing.md` · `success_metrics.md`.
