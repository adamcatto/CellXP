# Safety Model

> Status: Draft v0.1 — explanation. How CellXP stays safe by construction: early risk
> classification, refusal/escalation, the actionable-biology review gate, and audit. Binding rules
> live in `specs/agent/routing_policy.md`, `specs/agent/human_review_policy.md`, and `FR-33..35`;
> implementation in `agent/nodes/risk_classifier.py`, `domain/safety.py`.

## 1. Stance

We build a powerful tool over DNA/RNA/proteins/metabolites for legitimate research. Safety is **not**
a post-hoc filter; it is classified **early in the graph, before any capability runs** (`FR-34`), and
enforced at two layers: a **risk gate** (refuse/restrict) and a **human-review gate** (actionable
biology). Not for clinical/diagnostic use (`CR-5`).

## 2. Threat model (what we guard against)

- **Hazard enablement** — requests whose *primary purpose* is to create or enhance something
  dangerous (e.g. enhancing pathogen transmissibility/virulence, evading detection, toxin/biothreat
  design). Refused or escalated (`FR-33`).
- **Unsafe actionable output** — edits/designs/primers/origami presented as recommendations without
  human oversight. Gated (`human_review_policy.md`).
- **Silent incorrectness** — especially coordinate/assembly/strand errors that could mislead a wet-lab
  decision. Treated as a correctness-safety issue (`coordinate_systems.md`, `NFR-3`).
- **Out-of-domain / overreach** — clinical advice, non-DNA/RNA requests. Declined/redirected
  (`FR-8`, `CR-5`).

## 3. Risk classification (early gate)

`risk_classifier` runs before entity resolution/capabilities and assigns:

| Outcome | Meaning | Effect |
|---|---|---|
| `allow` | ordinary research request | proceed normally |
| `restrict` | sensitive but legitimate | proceed, but **force the review gate** on any actionable output, extra logging |
| `block` | primary purpose hazardous / disallowed | **refuse or escalate**; no capability work; explain + offer safe alternative (`FR-35`) |

Classification considers intent, entities (e.g. select agents/known hazards), and the *purpose*
signaled by the query — dual-use techniques are judged by intent and context, not by keyword alone,
to keep over-refusal low (`success_metrics.md` D5).

## 4. Refusal & escalation

- **Refuse** clearly hazardous requests with a brief, non-preachy explanation and, where possible, a
  safe alternative or redirection (`FR-35`).
- **Escalate** genuinely ambiguous high-stakes cases (configurable: human/operator review) rather
  than guessing.
- Refusals/escalations are logged to the audit trail (`specs/data/audit_log.md`).

## 5. The two gates together

```
query → risk_classifier ──block──▶ refuse/escalate → report (no capabilities)
                         ──restrict─▶ capabilities allowed, review gate forced
                         ──allow────▶ capabilities; review gate iff actionable
actionable output → human_review_gate → approve|reject|changes   (human_review_policy.md)
```

Approval at the review gate **cannot override** a safety `block` (`human_review_policy.md` §7).

## 6. Correctness as safety

A confidently-wrong coordinate or assembly could send a researcher to the wrong locus. Therefore:
coordinate/assembly/strand handling is explicit and validated (`coordinate_systems.md`); a silent
coordinate error is a release-blocking P0 (`NFR-3`); the target coordinate-error rate is **zero**
(`success_metrics.md` D1).

## 7. Privacy

User-uploaded sequences/data are treated as private; secrets come only from env; no secret/PII leaks
in logs or run traces (`NFR-7`). Provenance records *what* ran, not credentials.

## 8. Evaluation & guardrails

Safety is measured and gated in CI: hazard-refusal recall = 100%, over-refusal ≤ 5%, review-gate
enforcement = 100%, early-classification = 100% (`success_metrics.md` D5;
`specs/evaluation/safety_rubric.md`; `tests/integration/test_crispr_gate.py`,
`tests/unit/test_risk_classifier.py`). Guardrails must never regress.

## 9. Related specs

`specs/agent/routing_policy.md` · `specs/agent/human_review_policy.md` · `coordinate_systems.md` ·
`specs/product/product_requirements.md` (`FR-33..35`, `NFR-3/7`) · `specs/product/success_metrics.md`
· `specs/evaluation/safety_rubric.md` · ADR-0005.
