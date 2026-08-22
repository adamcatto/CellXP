# Testing Strategy

> Status: Draft v0.1. Normative contract for **automated verification** of CellXP — what to test,
> where tests live, and **when each tier runs**. Implementation mechanics:
> `.agents/guidelines/testing.md`. Golden-query **quality** evals (rubrics, TRR) remain in
> `specs/evaluation/evaluation_plan.md` and `evals/`; this spec covers the full verification
> pyramid including those evals as a tier. Satisfies `NFR-10` and the release gate in
> `product_requirements.md` §8.

## 1. Purpose

CellXP spans a Next.js client, FastAPI skill/policy runtime, pluggable harness adapters,
LangGraph compatibility workflows, biological services, async GPU workers,
and pluggable storage. A single `pytest` invocation is not enough. This spec defines:

1. **Tiers** — static analysis through browser e2e and model evals.
2. **Ownership** — which layer each tier exercises.
3. **Triggers** — what runs on every PR vs nightly vs on-demand.
4. **Gates** — what must pass before merge and before release.

**Tests vs evals.** *Tests* assert deterministic or tightly bounded behavior (schemas, coordinates,
routing, gates, API contracts). *Evals* score non-deterministic LLM outputs against rubrics on golden
queries (`evals/golden_queries/`). Both are required; evals are slower and run on a narrower trigger
set.

## 2. System map (what each tier touches)

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Browser (Playwright)          workspace, chat, SSE, artifacts, a11y   │
├─────────────────────────────────────────────────────────────────────────┤
│  API contract                  OpenAPI, TS client gen, SSE ordering    │
├─────────────────────────────────────────────────────────────────────────┤
│  Backend e2e                   HTTP → graph → services → storage       │
├─────────────────────────────────────────────────────────────────────────┤
│  Integration                   graph control flow, service fakes       │
├─────────────────────────────────────────────────────────────────────────┤
│  Unit                          domain, nodes, transforms, policies   │
├─────────────────────────────────────────────────────────────────────────┤
│  Static                        ruff, mypy, OpenAPI lint, secret scan   │
└─────────────────────────────────────────────────────────────────────────┘
                              ▲
                    Golden-query evals + rubrics (LLM)
                              ▲
                    GPU / live-model smoke (optional, manual)
```

## 3. Test tiers

| Tier | ID prefix | Tooling | Typical duration | Primary signal |
|---|---|---|---|---|
| **T0 — Static** | — | Ruff, mypy, OpenAPI validator, dependency audit | seconds | types, style, schema drift |
| **T1 — Unit** | `tests/unit/` | pytest | seconds–1 min | pure logic, invariants (`NFR-3`) |
| **T2 — Integration** | `tests/integration/` | pytest + fakes/in-memory deps | 1–5 min | graph routing, gates, service contracts |
| **T3 — API contract** | `tests/contract/` | pytest + schemathesis or openapi diff | 1–3 min | `API-*`, generated TS client (`API-9`) |
| **T4 — Backend e2e** | `tests/e2e/` | pytest + Testcontainers/compose + httpx | 5–20 min | full request paths, streaming, jobs |
| **T5 — Browser e2e** | `tests/browser/` | Playwright (Chromium primary) | 5–15 min | UI journeys, SSE client, a11y smoke |
| **T6 — Golden evals** | `evals/` | `evals/run_evals.py` + LangSmith (opt.) | 15–60+ min | TRR, rubrics (`NFR-10`) |
| **T7 — Live model** | `tests/live/` | pytest, marked `gpu` / `live` | 30 min–hours | real AlphaGenome, Boltz, etc. |
| **T8 — Perf / load** | `tests/perf/` | k6 or locust (future) | variable | `NFR-1`, `NFR-2` budgets |

T0–T5 are **automated tests**; T6 is **evaluation**; T7–T8 are **non-default** verification.

### 3.1 T1 — Unit

**Scope:** deterministic code with no network: coordinate validation, variant normalization, risk
classification, reducers, routing predicates, evidence merge, provenance builders, visualization
payload normalizers, audit-log writers (no secrets in payload).

**Rule:** every new `FR-*`/`NFR-*`/`CR-*` invariant that can be expressed without an LLM MUST have
at least one unit test. P0 classes (`NFR-3`, safety classifiers) MUST have edge-case fixtures.

### 3.2 T2 — Integration

**Scope:** skill registry/policy kernel and active harness adapters with **stubbed or recorded** LLM +
model services. Compatibility coverage also executes the LangGraph workflow. Exercises: safety
block, clarification pause/resume, human-review gate (`FR-25/26`), partial-results degradation
(`NFR-6`), tool/loop budgets, typed I/O, and compatibility parity.

**Rule:** every actionable capability MUST have a gate-enforcement integration test (pattern:
`tests/integration/test_crispr_gate.py`).

### 3.3 T3 — API contract

**Scope:** FastAPI OpenAPI document validity, breaking-change detection vs committed snapshot,
request/response examples, SSE event ordering and resume semantics (`API-4`, `API-5`), idempotency
headers (`API-2`). TypeScript client generation from OpenAPI MUST succeed and compile (`API-9`).

### 3.4 T4 — Backend e2e

**Scope:** real HTTP against a running API + Postgres + Redis + file-backed object store (compose or
Testcontainers). LLM and foundation models **mocked or recorded** unless explicitly in T7. Covers:
session lifecycle, chat submit → streamed events → artifact fetch, job polling, upload limits
(`API-8`), auth/ownership (`API-3`).

### 3.5 T5 — Browser e2e

**Scope:** critical user journeys in a real browser against a dev/staging stack:

- send chat message and see streamed response / activity log
- answer a clarification card; resume run
- open workspace artifact (genome track, structure viewer smoke)
- run inspector / provenance panel
- keyboard navigation + axe a11y smoke on core flows (`NFR-9`)

Visual regression (screenshot diff) is **optional** and SHOULD be limited to stable chrome, not
model-dependent scientific plots.

### 3.6 T6 — Golden evals

**Scope:** golden queries per capability (`evals/golden_queries/*.jsonl`), scored by rubrics in
`evals/rubrics/` and thresholds in `success_metrics.md`. Includes safety red-team cases
(`specs/evaluation/safety_rubric.md`). Not a substitute for T1–T2 gate tests.

### 3.7 T7 — Live model (out of default CI)

**Scope:** smoke tests against real external model endpoints or on-GPU workers. Validates adapter
contracts, latency budgets, and coordinate round-trips with live inference. **Never required for
PR merge**; run on model-version bumps, infrastructure changes, and pre-release.

### 3.8 T8 — Performance (out of default CI)

**Scope:** SSE time-to-first-token, job queue throughput, tile endpoint latency. Run weekly or before
major releases.

## 4. Repository layout

| Path | Tier | Notes |
|---|---|---|
| `tests/unit/` | T1 | mirrors `src/backend/cellxp/{domain,services,agent}` |
| `tests/integration/` | T2 | graph + service integration |
| `tests/contract/` | T3 | OpenAPI / client compatibility |
| `tests/e2e/` | T4 | backend-only end-to-end |
| `tests/browser/` | T5 | Playwright specs + `playwright.config.ts` |
| `tests/fixtures/` | all | JSON, FASTA, recorded LLM/model responses |
| `tests/live/` | T7 | opt-in; excluded from default `make test` |
| `tests/perf/` | T8 | future |
| `evals/` | T6 | golden queries, rubrics, runner |

Frontend **component/unit** tests (Vitest + Testing Library) live under `src/frontend/` when added;
they follow the same trigger rules as T1 for UI logic.

## 5. When to run each tier

### 5.1 Default CI (every PR + push to `main`)

| Tier | Runs | Blocks merge |
|---|---|---|
| T0 Static | yes | yes |
| T1 Unit | yes | yes |
| T2 Integration | yes (full or affected; see §5.3) | yes |
| T3 Contract | yes if `src/backend/cellxp/api/` or OpenAPI snapshot touched | yes when triggered |
| T4 Backend e2e | **subset** smoke (≤ 3 min); full suite on `main` | smoke yes |
| T5 Browser | **no** (too slow for every PR) | — |
| T6 Evals | **no** | — |
| T7 Live | **no** | — |
| T8 Perf | **no** | — |

### 5.2 Scheduled / pipeline tiers

| Tier | Schedule | Also run when |
|---|---|---|
| T4 full backend e2e | nightly on `main` | `specs/agent/*`, `specs/interface/*`, storage/jobs paths change |
| T5 Browser e2e | nightly on `main` | `src/frontend/**`, `specs/interface/{chat,workspace,genome_browser,streaming}*` |
| T6 Golden evals | nightly on `main` | `specs/agent/**`, `specs/services/llm*`, prompts, policy kernel, harness adapters, capability skills/workflows |
| T7 Live model | weekly + manual `workflow_dispatch` | model version bump, `specs/services/*`, worker/GPU infra |
| T8 Perf | weekly | API streaming, job worker, visualization tiling changes |

### 5.3 Path-based triggers (PR scope)

When CI supports it, **affected-tier** runs reduce noise:

| Changed paths (examples) | Minimum extra tiers beyond T0+T1 |
|---|---|
| `src/backend/cellxp/domain/**`, `specs/biology/*` | T1 coordinates + relevant integration |
| `src/backend/cellxp/agent/**`, `specs/agent/**` | T2 full integration smoke + T6 (nightly) |
| `src/backend/cellxp/api/**`, `specs/interface/api_contracts.md` | T3 + T4 smoke |
| `src/backend/cellxp/services/<cap>/**` | T2 for capability + golden queries for domain |
| `src/frontend/**` | frontend unit (when present) + T5 (nightly) |
| `src/backend/cellxp/jobs/**`, GPU workers | T4 job path + T7 (manual) |
| `evals/**`, `specs/evaluation/**` | T6 |
| docs-only (`documentation/**`, `specs/**` without code) | T0 only |

Contributors SHOULD run the **locally relevant** tiers before push (see guideline).

### 5.4 Release gate (v1)

Before tagging a release candidate:

1. T0–T5 all green on `main` (latest nightly inclusive).
2. T6 golden evals meet thresholds in `success_metrics.md`.
3. T7 smoke passed for every **shipped** external model in the last 7 days.
4. Zero open P0s on `NFR-3` and safety `FR-33..35` test classes.
5. Every shipped `FR-*` MUST has automated coverage (T1–T4 or T6 as appropriate).

## 6. Requirements (testable)

- **TST-1** T0 static checks (ruff, mypy, OpenAPI validity) MUST run on every PR and block merge.
- **TST-2** T1 unit tests MUST run on every PR and block merge; default `make test` MUST exclude T7
  and T8.
- **TST-3** Coordinate, strand, and assembly invariants (`NFR-3`) MUST be covered by T1 tests with
  explicit edge fixtures per organism class in `supported_species.md`.
- **TST-4** Human-review and safety routing (`FR-25/26`, `FR-33..35`) MUST be covered by T2
  integration tests per actionable capability.
- **TST-5** API OpenAPI document and generated TypeScript client (`API-9`) MUST be validated by T3
  on any API schema change.
- **TST-6** T4 MUST include at least one streaming chat path test and one artifact fetch test using
  real storage backends (not mocks).
- **TST-7** T5 MUST cover chat submit, clarification resume, and one artifact viewer smoke before
  release; axe MUST run on the chat and workspace shells.
- **TST-8** T6 golden evals MUST run nightly and on agent/LLM/harness changes; regressions beyond
  `success_metrics.md` thresholds block release (not necessarily every PR).
- **TST-9** T7 live-model tests MUST be marked `gpu` or `live` and MUST NOT be required for PR merge.
- **TST-10** Test fixtures MUST NOT contain secrets or real private patient data; use synthetic or
  public reference sequences only.
- **TST-11** Flaky tests MUST be fixed or quarantined within one sprint; quarantined tests MUST NOT
  block release without an explicit waiver in `specs/planning/open_questions.md`.
- **TST-12** Adding a capability (`CONTRIBUTING.md` §2) MUST add: T1 for transforms, T2 smoke, golden
  queries in T6, and path entries in §5.3 of this spec.

## 7. Traceability

| Requirement | Primary tiers |
|---|---|
| `NFR-3` | T1, T6 audit |
| `NFR-6` | T2, T4 |
| `NFR-9` | T5 (axe) |
| `NFR-10` | T6 |
| `API-9` | T3 |
| `FR-25/26` | T2, T5 |
| `FR-33..35` | T1, T2, T6 safety rubric |
| Release §8 | T0–T7 per §5.4 |

## 8. Related

`specs/evaluation/evaluation_plan.md` · `specs/evaluation/regression_tests.md` ·
`specs/evaluation/golden_query_sets.md` · `specs/product/product_requirements.md` (`NFR-10`) ·
`specs/product/success_metrics.md` · `.agents/guidelines/testing.md` · `CONTRIBUTING.md` ·
`.agents/guidelines/langgraph.md` (graph testing) · `.agents/guidelines/langsmith.md` (eval CI).
