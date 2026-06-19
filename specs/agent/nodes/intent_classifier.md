# intent_classifier Node

> Status: Draft v0.1. Node 2. Parent: `graph_spec.md` §4, `routing_policy.md` §2. Impl:
> `agent/nodes/intent_classifier.py`. LLM-backed.

## Purpose

Classify the query (+ normalized inputs) into a primary intent and optional secondary intents that
drive plan selection.

## Reads → Writes

- **Reads:** `user_query`, `normalized_inputs`, `messages`.
- **Writes:** `intent` (last-write-wins).

## Behavior

1. Map the request to an intent from the controlled set (`routing_policy.md` §2):
   `variant_effect | gwas_qtl | crispr_design | annotation | binding | structure | origami |
   inverse_edit_design | systems_analysis | literature | visualization | out_of_domain | ambiguous`.
2. Emit secondary intents for multi-capability requests (e.g. "annotate + design guides").
3. Attach a confidence; low confidence → bias toward `ambiguous` (triggers clarification downstream).
4. Use inputs as signal: a pasted protein sequence with "what is this?" → `structure`/`annotation`,
   etc.

## Errors / edge cases

- Off-domain (non-DNA/RNA/protein/metabolite) → `out_of_domain` → refuse/redirect (`FR-8`).
- Genuinely multi-intent → return the set; planner decides macro vs composed.

## Prompt

`agent/prompts/supervisor.md` (intent section). Keep the label set in sync with `routing_policy.md`.

## Open questions

- Single classifier vs hierarchical (domain → capability).
- Calibration of the confidence used to gate clarification.

## Related

`routing_policy.md` §2 · `risk_classifier.md` · `planner.md`.
