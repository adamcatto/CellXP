# Routing Policy

> Status: Draft v0.1. Defines how a query becomes a plan and how the agent decides *how much to
> plan*: intent classification, macro matching, atomic vs composed planning, subtask routing, and
> clarification/refusal branches. Consumes `state_schema.md` and `graph_spec.md`; pairs with
> `tool_use_policy.md` (which *model* runs a subtask). Implementation: `agent/nodes/intent_classifier.py`,
> `nodes/planner.py`, `nodes/task_selector.py`, `agent/routing.py`.

## 1. Decision pipeline

```
query+inputs → intent → risk → entities(resolve|ask) → PLAN SELECTION → subtask routing → loop
```

Plan selection chooses exactly one of: **refuse**, **clarify**, **macro**, **atomic**, **composed**
(`task_patterns.md` §0).

## 2. Intent classification

`intent_classifier` maps the query to a primary intent + optional secondary intents:

| Intent | Typical capability/subgraph |
|---|---|
| `variant_effect` | variant_effect |
| `gwas_qtl` | gwas |
| `crispr_design` | crispr (actionable) |
| `annotation` | annotation |
| `binding` | binding |
| `structure` | structure |
| `origami` | origami (actionable) |
| `inverse_edit_design` | composed (variant_effect ⇄ crispr) |
| `systems_analysis` | composed (networks/metabolic) |
| `literature` | rag |
| `visualization` | visualization |
| `out_of_domain` | → refuse/redirect (`FR-8`) |
| `ambiguous` | → clarify |

Multi-intent queries (e.g. "annotate this and design guides") yield multiple intents → a composed or
macro plan. The classifier records confidence; low confidence biases toward clarification.

## 3. Risk gate (before planning)

`risk_classifier` runs **before** capability planning (`FR-34`). Outcomes:
- `block` → refuse/escalate, skip to report (`safety_model.md`).
- `restrict` → allow analysis but force review gate on any actionable output.
- `allow` → proceed.

Routing never plans capability work for a `block` result.

## 4. Entity resolution & clarification

`entity_resolver` must establish everything coordinate-dependent work needs — especially **organism +
assembly** (`FR-11`, `coordinate_systems.md`). Rules:
- If a required entity is unresolved/ambiguous and consequential → emit a **blocking**
  `Clarification`; route to `await_input` (do not guess).
- If inference is safe and low-stakes (e.g. obvious default assembly with a note) → proceed and record
  the assumption.
- Prefer **one** well-targeted question over many (`FR-7`); batch related clarifications.

Consequential parameters that SHOULD trigger a question rather than a guess: organism, assembly,
edit intent/target, tissue/cell-type when it changes the answer.

## 5. Plan selection

`planner` picks the plan kind in this priority order:

1. **Refuse** — `risk=block` or `intent=out_of_domain`.
2. **Clarify** — unresolved blocking entities / `intent=ambiguous`.
3. **Macro match** — the query matches a registered macro's trigger (§6) → `plan.kind="macro"`.
4. **Atomic** — a single intent mapping to one capability with no cross-capability dependencies →
   `plan.kind="atomic"` (one subtask, fixed internal pipeline).
5. **Composed** — multiple intents, dependencies, loops, or a systems-level pattern → build a subtask
   DAG dynamically → `plan.kind="composed"`.

The planner records a brief `rationale` and may set/raise `plan.revision` when it replans mid-run.

## 6. Macro matching

A **macro** is a registered, parameterized recipe (definition owned by the macro registry —
`specs/data/relational_schema.md`; referenced in state by `macro_id`). Matching:

- Each macro declares **triggers**: intent set, required entity types, and/or example phrasings.
- `planner` selects a macro when triggers match and required parameters are resolvable from
  `entities`/`normalized_inputs`.
- On match, the macro's pre-baked `subtasks` (with `depends_on`) are expanded into state; the agent
  **skips free-form planning**.
- A macro may declare **optional/adaptive** subtasks the planner can include/skip based on inputs.
- If a matched macro can't be fully parameterized → fall back to clarify or composed planning.

**Promotion:** a frequently-run composed plan whose shape stabilizes can be saved as a macro
(`task_patterns.md` §0.3); user-saved macros are scoped to the user.

## 7. Subtask decomposition (composed)

For composed plans, the planner decomposes the goal into a `Subtask` DAG:
- Each subtask names a `capability`/`type`, its `inputs` (refs into `entities`/`normalized_inputs`),
  and `depends_on`.
- Mark `is_actionable=true` on subtasks that produce edits/designs/primers/origami (forces the gate).
- Systems-level patterns instantiate the recipes in `task_patterns.md` §2–§6 (e.g. variant→GRN,
  strain engineering); inverse-design loops are expressed as subtasks the planner re-adds on
  re-entry until a budget/convergence criterion is met (`state_schema.md` §15).

## 8. Subtask routing (`task_selector` + `route_task`)

- `task_selector` selects the next **ready** subtask (all `depends_on` complete) and routes via
  `route_task` (`agent/routing.py`) to the matching subgraph.
- Independent ready subtasks MAY be dispatched concurrently (`graph_spec.md` §9).
- When a subtask is `is_actionable` and has produced output, route to `human_review_gate` before
  treating it as recommended.
- When no subtasks remain (or budget hit) → route to `critic` → `report_generator`.

Current `route_task` maps `subtasks[0].type`; target maps `cursor.active_subtask_id`'s type, with
`report_generator` as the default/terminal destination.

## 9. Replanning

Triggers for `planner` re-entry (raising `plan.revision`):
- a subtask failed but an alternative capability/model exists (`tool_use_policy.md` fallbacks);
- `critic` flags insufficient/contradictory evidence and a further subtask could resolve it;
- an inverse-design/systems loop needs another iteration and budget remains.

Replanning MUST respect `budget` and avoid cycles (cap revisions).

## 10. Defaults & precedence summary

1. Safety (`block`) overrides everything.
2. Clarify over guess for consequential params.
3. Macro over ad-hoc plan when triggers match (reproducibility/speed).
4. Atomic over composed when one capability suffices (simplicity).
5. Concurrency over serial when subtasks are independent (latency).

## 11. Open questions

- Macro trigger matching: rules/keywords vs an LLM classifier vs hybrid? (lean hybrid: LLM intent +
  declarative trigger constraints.)
- How aggressively to auto-infer assembly vs ask (per-organism defaults?).
- Replanning revision cap value and convergence criteria for inverse-design loops.

## 12. Related specs

`state_schema.md` · `graph_spec.md` · `tool_use_policy.md` · `human_review_policy.md` ·
`safety_model.md` · `task_patterns.md` · `coordinate_systems.md`.
