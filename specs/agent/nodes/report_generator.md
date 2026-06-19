# report_generator Node

> Status: Draft v0.1. Node 10 — terminal. Parent: `graph_spec.md` §4, `state_schema.md` §11. Impl:
> `agent/nodes/report_generator.py`, prompt `agent/prompts/report_writer.md`. LLM-backed.

## Purpose

Synthesize the final, cited, confidence-qualified answer and assemble the `Report` the UI renders.

## Reads → Writes

- **Reads:** reconciled `evidence`, `citation_map`, `confidence_summary`, `artifacts`, `subtasks`,
  `review`.
- **Writes:** `final_report` (`Report`), `status=completed`, may append a `message`.

## Behavior

1. Write `Report.markdown` where **every substantive sentence carries a citation marker** resolving to
   evidence (`evidence_and_confidence.md`); uncited substantive claims are disallowed.
2. Feature relevant `artifact_ids`; include `confidence_summary` and `limitations`.
3. Add `suggested_followups` (agentic next steps/experiments; `mission.md` §3).
4. Respect review state: actionable items appear as recommendations only if approved; otherwise as
   gated candidates (`human_review_policy.md`).
5. Prefer "insufficient evidence" over fabrication when evidence is thin (`mission.md` §5).

## Errors / edge cases

- Partial runs (failed subtasks) → report what exists + clearly state gaps (`NFR-6`).
- No usable evidence → explain why + suggest how to proceed.

## Open questions

- Streaming granularity of `report.delta` (sentence vs token).
- Report templating per capability vs free-form.

## Related

`state_schema.md` §11 · `evidence_and_confidence.md` · `human_review_policy.md` ·
`specs/interface/streaming_protocol.md` · `specs/interface/chat_interface.md` ·
`specs/interface/artifact_model.md`.
