# Evaluation Plan

> Status: Draft v0.1. Defines **quality measurement** of agent outputs (golden queries, rubrics, TRR).
> **Automated verification** tiers (unit, integration, e2e, Playwright, CI triggers) are in
> `testing_strategy.md`; implementation how-to in `.agents/guidelines/testing.md`.

## 1. Scope

**In scope (this doc + `evals/`):** non-deterministic LLM behavior, biological correctness, response
quality, provenance completeness, safety posture — scored on golden queries against rubrics.

**Out of scope:** deterministic invariants (coordinates, gates, API schemas) — those are **tests**
(`tests/`, `TST-*`), though eval audits may cross-check the same metrics (`success_metrics.md`).

## 2. Assets

| Asset | Location |
|---|---|
| Golden queries | `evals/golden_queries/*.jsonl` |
| Rubrics | `evals/rubrics/*.md` + `specs/evaluation/*_rubric.md` |
| Runner | `evals/run_evals.py` |
| Thresholds | `specs/product/success_metrics.md` |

## 3. Execution (T6)

- **Nightly** on `main` and on changes to agent, LLM service, harness, or prompts
  (`testing_strategy.md` §5.2).
- **Pre-release** full run required (`TST-8`, product_requirements §8).
- Optional LangSmith tracing per `.agents/guidelines/langsmith.md`.

Deployed runs are captured before rubric scoring:

```bash
python evals/run_evals.py dispatch \
  --api-base-url http://localhost:8000/api/v1 \
  --archive-dir evals/reports/runs/<deployment>-<timestamp>
```

The archive directory MUST be new and is never overwritten. Its manifest records catalog hashes,
the result JSONL hash, build revision (`CELLXP_BUILD_REVISION`), API endpoint, timestamps, run IDs,
and dispatch errors. Dispatch errors remain unscored/missing evidence and therefore fail closed.
Rubric/domain-review and authorized private safety scores are separate inputs; the runner does not
infer or fabricate them from deterministic shape checks.

Deployed acceptance for review/audit/export and run-inspector deep links is collected with
`python -m evals.deployed_acceptance`. The collector archives every endpoint observation and emits
only measured `acceptance.review_approve_audit` and `acceptance.run_inspector_deep_link` values.
Missing audit/export/deep-link endpoints fail closed. Its two-run telemetry sample MUST NOT populate
the release-scale reliability or latency fields.

## 4. Related

`testing_strategy.md` · `regression_tests.md` · `golden_query_sets.md` · `safety_rubric.md` ·
`biological_correctness_rubric.md` · `success_metrics.md`.
