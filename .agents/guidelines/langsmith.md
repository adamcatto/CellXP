# LangSmith Implementation Guidelines

Observability, evaluation, and the data flywheel. Specs: `documentation/explanation/post_training.md`,
`specs/product/success_metrics.md`.

## What we use it for

1. **Tracing** every run/sub-agent for debugging and auditability.
2. **Evals** — gating model/prompt changes on a held-out suite before they ship.
3. **Datasets** — curating trajectories for post-training (`post_training.md`).

## Tracing

- Enable via env (`LANGSMITH_TRACING=true`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`) — config-only,
  off by default in local/offline mode (privacy: traces may contain sequence data; see `specs/data/*`).
- Trace LangGraph runs end-to-end; tag traces with `run_id`, `session_id`, `session_type`, capability,
  and organism so we can slice metrics (e.g. wrong-organism model selection).
- Record the **provenance-relevant** metadata we already keep (`Step.tool`/`tool_version`/params) so a
  LangSmith trace and our internal trace agree.

## Evals (gate changes)

- Maintain dataset suites per capability + cross-cutting suites for trust/safety. Map evaluators to
  `success_metrics.md`:
  - task correctness (vs `specs/biology/*` reference expectations),
  - **organism-appropriate model selection** (hard rule),
  - citation validity + evidence completeness,
  - confidence calibration (ECE),
  - safety recall + over-refusal rate,
  - tool-call validity / retry rate, latency, cost.
- A prompt/model/graph change ships only if it beats the incumbent on trust + safety **without
  regressions**. Wire eval runs into CI for spec-affecting changes.

## Datasets & the flywheel

```
runs → traces → filter (review decisions + eval scores + safety labels) → datasets
     → SFT / DPO / distillation (post_training.md) → eval gates → ship
```

- Positive examples: reviewer-**approved**, high-eval trajectories.
- Negative/preference examples: **rejected** actionable proposals, critic-caught errors, uncited
  claims, wrong-organism selections, over/under-refusals.
- De-identify/govern training data per the retention & consent policy (`specs/data/*`).

## Don't

- Don't enable cloud tracing in a deployment handling private data without explicit consent/config.
- Don't ship a checkpoint that regresses safety recall or over-refusal, even if task metrics improve.
- Don't let eval datasets leak into training data (contamination).
