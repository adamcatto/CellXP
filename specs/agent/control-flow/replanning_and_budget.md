# Replanning & Budget

> Status: Draft v0.1. When the agent revises its plan, how looped/composed tasks iterate, and the
> ceilings that bound them. Plan model: `state_schema.md` §6/§15; triggers: `routing_policy.md` §9.

## 1. Replanning triggers

`planner` is re-entered (raising `plan.revision`) when:
- a subtask **failed** but an alternative capability/model exists (`tool_use_policy.md` §7 fallbacks);
- `critic` flags **insufficient/contradictory** evidence and a further subtask could resolve it
  (`evidence_integration.md` §10);
- a **loop** task (inverse design, systems optimization) needs another iteration and budget remains;
- a **review** decision was `changes_requested` (`human_review_policy.md`).

## 2. Loops (composed/inverse-design)

Looped patterns (`task_patterns.md` §6, `FR-18c`) are expressed as subtasks the planner **re-adds**
on re-entry (propose → score → select → repeat) until a **convergence criterion** or **budget** stop.
Each iteration's intermediate artifacts remain inspectable (`evidence_integration.md` §8).

## 3. Budget ceilings

`Budget{max_tokens, max_wallclock_s, max_cost_usd}` (`state_schema.md` §15) bounds every run; `spent`
tracks running totals. The planner/`task_selector` check budget before dispatch and before each loop
iteration. Hitting a ceiling → stop dispatch, integrate + report partial results (`NFR-6`).

## 4. Anti-cycle safeguards

- A **revision cap** limits total replans per run.
- Loops must declare a convergence/iteration cap; no unbounded self-extension.
- Repeated identical failures short-circuit to a reported gap rather than retrying forever.

## 5. Reproducibility

Each plan revision + the reason is recorded (`plan.revision`, rationale) so the decision path is part
of the reproducible trace (`FR-24`).

## 6. Open questions

- Default revision cap and loop iteration caps.
- Convergence metrics for inverse-design/systems loops (effect plateau? off-target floor?).
- Per-budget defaults by plan kind / persona.

## 7. Related

`routing_policy.md` §9 · `state_schema.md` §6/§15 · `task_patterns.md` §6 · `concurrency.md` ·
`tool_use_policy.md` §7.
