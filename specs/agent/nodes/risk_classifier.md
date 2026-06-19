# risk_classifier Node

> Status: Draft v0.1. Node 3 — runs **before** capabilities (`FR-34`). Parent: `graph_spec.md` §3/§6,
> `safety_model.md`. Impl: `agent/nodes/risk_classifier.py`, `domain/safety.py`. LLM + rules.

## Purpose

Assign a safety risk level early so hazardous requests never reach capability execution and sensitive
ones are forced through the review gate.

## Reads → Writes

- **Reads:** `user_query`, `intent`, `normalized_inputs`, `entities` (if available).
- **Writes:** `risk` (`RiskAssessment`, last-write-wins); may set `status`/route to refusal.

## Behavior

1. Classify into `allow | restrict | block` (`safety_model.md` §3) judging **purpose + context**, not
   keywords alone (dual-use techniques are normal research; intent decides).
2. `block` → route to refusal/escalation; no capability planning (`FR-33/35`).
3. `restrict` → proceed but set a flag forcing the human-review gate on any actionable output and
   enabling extra audit logging.
4. `allow` → proceed normally.
5. Record rationale + any matched hazard signals into the trace/audit (`specs/data/audit_log.md`).

## Errors / edge cases

- Ambiguous high-stakes → `block` with escalation rather than guessing `allow`.
- Keep over-refusal low (≤5%, `success_metrics.md` D5) while recall stays at 100%.

## Prompt

`agent/prompts/supervisor.md` (safety section) + deterministic rules in `domain/safety.py`.

## Open questions

- Hazard taxonomy + escalation routing (who reviews escalations).
- Per-capability thresholds escalating "restrict" → "block".

## Related

`safety_model.md` · `routing_policy.md` §3 · `human_review_policy.md` §7 ·
`tests/unit/test_risk_classifier.py`.
