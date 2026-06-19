# Run Lifecycle

> Status: Draft v0.1. States and transitions for a run and its tasks. Types: `state_schema.md`
> §14.

## 1. RunStatus

```
queued → running ⇄ (awaiting_input | awaiting_review) → running → completed
                                                              ↘ failed
                                                              ↘ cancelled
```

| State | Meaning | Exit |
|---|---|---|
| `queued` | accepted, not started | scheduler starts → `running` |
| `running` | actively executing nodes | pause / finish / error |
| `awaiting_input` | open blocking `Clarification` | user answers → `running` |
| `awaiting_review` | pending `ReviewState` | decision → `running` |
| `completed` | report produced (incl. partial) | terminal |
| `failed` | fatal error | terminal |
| `cancelled` | user/operator cancelled | terminal |

`awaiting_*` states are durable (checkpointed; `specs/data/*`) so a run can resume later.

## 2. TaskStatus (per subtask/step)

```
pending → running → done | failed | skipped | needs_review
```

- `failed` (recoverable) does not fail the run — partial results continue (`NFR-6`).
- `needs_review` marks an actionable subtask awaiting the gate.
- `skipped` for unsatisfiable-dependency or out-of-budget subtasks.

## 3. Transitions emit events

Each state change emits a streaming event (`run.status`, `subtask.updated`, `step.*`;
`state_schema.md` §17) consumed by the API/UI (`api_contracts.md`).

## 4. Cancellation

A cancel request sets `cancelled`, stops dispatch, lets in-flight heavy jobs settle or abort
(`jobs/*`), and persists the partial trace.

## 5. Related

`state_schema.md` §14 · `pause_and_resume.md` · `control_flow_overview.md` · `api_contracts.md`.
