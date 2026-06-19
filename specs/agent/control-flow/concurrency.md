# Concurrency

> Status: Draft v0.1. How independent work runs in parallel safely. Reducers: `state_schema.md` §16;
> jobs: `architecture_overview.md` §7.

## 1. Two kinds of parallelism

1. **Parallel subtasks** — independent ready subtasks (no shared `depends_on`) MAY be dispatched
   concurrently by `task_selector` (e.g. variant_effect + gwas for the same locus).
2. **Async heavy steps** — `tier="heavy"` steps (GPU/large models, genome-wide scans) run as jobs;
   the subgraph awaits results without blocking the top-level loop (`tool_use_policy.md` §6).

## 2. Safe state writes

Concurrent nodes MUST write only **append** (`messages`, `steps`, `evidence`, `artifacts`, `errors`)
or **merge-by-id** (`entities`, `clarifications`) fields. Single-owner, last-write-wins fields
(`plan`, `cursor`, `status`, `final_report`, …) MUST NOT be written from parallel branches
(`state_schema.md` §16). Violations risk clobbering and are a correctness bug.

## 3. Liveness during long work

Heavy steps stream liveness via `run.status` / `step.started` / `step.finished` events so the UI shows
progress within ~2 s of a state change (`NFR-1`, `success_metrics.md` D4). The run never appears
frozen while a job runs.

## 4. Ordering & joins

- Dependent subtasks (`depends_on`) serialize naturally via readiness checks.
- A join point (e.g. `evidence_integrator`) consumes the appended outputs of all completed parallel
  branches; it is idempotent and re-runnable.

## 5. Limits

Concurrency degree is bounded by `budget` and worker/GPU capacity (`jobs/*`). Inverse-design and
systems loops cap iterations (`replanning_and_budget.md`).

## 6. Related

`state_schema.md` §16 · `tool_use_policy.md` §6 · `graph_spec.md` §9 ·
`architecture_overview.md` §7 · `replanning_and_budget.md`.
