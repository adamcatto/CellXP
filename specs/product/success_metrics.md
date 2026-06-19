# Success Metrics

> Status: Draft v0.1. Defines how we measure whether CellXP fulfills its mission and
> requirements. Operationalizes the north-star metric from `mission.md` and the acceptance bar from
> `product_requirements.md`. Measurement mechanics (golden queries, rubrics, harness) live in
> `evals/` and `specs/evaluation/`. Targets are **initial** and SHOULD be recalibrated after the
> first real baseline.

## 1. North-star metric

**Trustworthy Resolution Rate (TRR).** The fraction of in-domain queries that produce an answer the
user accepts as correct **and** adequately evidenced (cited + confidence-qualified +
provenance-complete) **without manual rework**.

```
TRR = (# queries: correct AND well-evidenced AND no rework) / (# in-domain queries)
```

A query counts toward TRR only if all three hold: (a) biologically correct per rubric, (b)
provenance-complete per the evidence model, (c) the user did not have to redo the work elsewhere.

- **v1 target:** TRR ≥ 0.70 on the golden-query set; ≥ 0.60 self-reported in real usage.
- **Why this metric:** it fuses correctness, trust, and usefulness into one number; gaming any single
  factor (e.g. confident-but-wrong, or right-but-unsourced) does not move it.

## 2. Metric framework

We track five dimensions. Each maps to requirements and to an evaluation source.

| # | Dimension | Question it answers |
|---|---|---|
| D1 | Correctness | Are the answers biologically right? |
| D2 | Trust & provenance | Can users verify and reproduce them? |
| D3 | Usefulness & adoption | Do people get value and come back? |
| D4 | Performance & reliability | Is it fast and dependable enough? |
| D5 | Safety | Do we refuse what we must, and only that? |

---

## 3. D1 — Correctness

| Metric | Definition | v1 target | Source |
|---|---|---|---|
| Golden-query accuracy | % golden queries passing the biological-correctness rubric | ≥ 75% | `evals/golden_queries/`, `rubrics/biological_correctness.md` |
| Coordinate-error rate | % runs with any assembly/strand/base error (P0 class) | **0%** | `tests/unit/test_coordinate_validation.py`, eval audit |
| Organism-appropriate model selection | % runs selecting an oracle valid for the organism (e.g. never AlphaGenome on bacteria) | **100%** | `specs/agent/tool_use_policy.md` §4, eval audit |
| Per-capability pass rate | rubric pass rate within each capability domain | ≥ 70% each | golden sets per domain |
| Hallucination rate | % answers asserting a claim unsupported by evidence | ≤ 3% | provenance rubric |

> Coordinate errors are a release blocker (NFR-3): the target is zero, not "low".

## 4. D2 — Trust & provenance

| Metric | Definition | v1 target | Source |
|---|---|---|---|
| Provenance completeness | % claims with linked evidence (model/DB/citation) | ≥ 95% | `rubrics/provenance.md`, FR-22 |
| Confidence coverage | % predictions carrying an explicit confidence indicator | 100% | FR-23 |
| Reproducibility rate | % re-runs producing equivalent results (within model nondeterminism) | ≥ 95% | FR-32/NFR-4, re-run harness |
| Run-trace completeness | % runs with full inspectable trace (inputs→tools→outputs) | 100% | FR-24, FR-30 |
| Citation validity | % citations that resolve and support the claim | ≥ 95% | RAG eval |

## 5. D3 — Usefulness & adoption

| Metric | Definition | v1 target | Source |
|---|---|---|---|
| Task completion rate | % sessions where the user reaches a satisfactory answer | ≥ 70% | product analytics |
| Time-to-first-answer (perceived) | submit → first useful artifact/answer | see D4 (NFR-1) | analytics |
| Artifact export rate | % answers whose artifact is exported/shared | ≥ 25% | analytics, FR-28 |
| Rework rate | % answers the user redid elsewhere | ≤ 20% | survey + analytics |
| Return usage | % users with a session in the following week (early signal) | ≥ 40% | analytics |
| Clarification quality | % clarifying questions users rate as helpful (not noise) | ≥ 80% | feedback, FR-7 |
| User satisfaction (CSAT) | thumbs-up / explicit rating on answers | ≥ 4.0/5 | in-app feedback |

## 6. D4 — Performance & reliability

| Metric | Definition | v1 target | Source |
|---|---|---|---|
| Time-to-first-token/plan | submit → first streamed plan/token | ≤ 3 s p50, ≤ 6 s p95 | tracing, NFR-1 |
| Lightweight query latency | end-to-end for non-GPU capabilities (e.g. lookup/annotation) | ≤ 15 s p50 | tracing |
| Long-job liveness | GPU/async jobs show progress within | ≤ 2 s of state change | NFR-1, NFR-2 |
| Tool-call / structured-output validity | % LLM plan/tool outputs schema-valid on first try (low retry) | ≥ 95% | tracing, `HARN-3` |
| Run success rate | % runs completing without unhandled error | ≥ 98% | observability, NFR-6 |
| Graceful degradation | % single-service failures yielding partial-result (not crash) | ≥ 95% | chaos/integration tests, NFR-6 |
| API availability | API uptime | ≥ 99.5% | ops monitoring |

## 7. D5 — Safety

| Metric | Definition | v1 target | Source |
|---|---|---|---|
| Hazard refusal recall | % genuinely hazardous requests correctly refused/escalated | 100% | `rubrics/safety.md`, FR-33 |
| Over-refusal (false-positive) rate | % benign requests wrongly refused | ≤ 5% | safety eval |
| Review-gate enforcement | % actionable outputs that pass through the gate | 100% | `tests/integration/test_crispr_gate.py`, FR-25/26 |
| Early-classification rate | % runs where safety is classified before capability execution | 100% | FR-34 |

> Safety recall has zero tolerance for misses; the trade-off knob is over-refusal, kept low but
> always subordinate to recall.

---

## 8. Guardrail metrics (must not regress)

Even if headline metrics improve, these must hold: coordinate-error rate = 0; organism-appropriate
model selection = 100%; hazard refusal recall = 100%; review-gate enforcement = 100%; run-trace
completeness = 100%. A change that regresses any guardrail is not shippable regardless of other gains.

## 9. Measurement cadence & ownership

- **Per-PR (CI):** golden-query subset, coordinate tests, safety + review-gate tests, provenance
  checks (`.github/workflows/evals.yml`, `ci.yml`). Block merge on guardrail regressions.
- **Per-release:** full golden-query suite + all rubrics; report the metric framework table.
- **Continuous (post-launch):** D3/D4 analytics + D5 production monitoring; weekly review.
- Targets are revisited after the first baseline; changes recorded here with date + rationale.

## 10. Release gate (ties to PRD §8)

A v1 release candidate ships only when: D1 golden accuracy ≥ 75% and per-capability ≥ 70%; all D2
provenance/confidence/trace targets met; all D5 safety targets met (with guardrails at 100%); D4
run-success ≥ 98% and latency p50/p95 within target; and no open P0 (coordinate/safety) defects.

## 11. Traceability

D1 ↔ `specs/evaluation/biological_correctness_rubric.md`; D2 ↔ `evidence_and_confidence.md`,
`specs/data/provenance_model.md`; D4 ↔ `architecture_overview.md` (jobs/async), NFRs; D5 ↔
`safety_model.md`, `specs/evaluation/safety_rubric.md`. Golden queries seeded from
`specs/product/user_stories.md` (marked *golden seed*).
