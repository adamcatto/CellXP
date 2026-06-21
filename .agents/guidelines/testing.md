# Testing Guidelines

How to **write and run** CellXP's verification suite. Normative tier definitions, triggers, and
release gates: `specs/evaluation/testing_strategy.md` (`TST-*`).

## When to use this doc

- Adding or fixing tests in `tests/` or `evals/`
- Choosing what to run locally before a PR
- Setting up Playwright, pytest markers, fixtures, or CI jobs
- Extending coverage for a new capability, API route, or UI flow

Stack defaults: **pytest 8+** (backend), **Playwright** (browser e2e), **Vitest** (frontend unit,
when introduced). See `architecture_overview.md` §2.

## Directory layout

```
tests/
  unit/           # T1 — fast, no I/O
  integration/    # T2 — graph + services with fakes
  contract/       # T3 — OpenAPI / TS client
  e2e/            # T4 — API + real infra, mocked models
  browser/        # T5 — Playwright
  fixtures/       # shared JSON, FASTA, recorded responses
  live/           # T7 — opt-in gpu/live
  perf/           # T8 — future
evals/
  golden_queries/ # T6 inputs
  rubrics/        # T6 scoring docs
  run_evals.py    # T6 entrypoint
src/frontend/     # Vitest colocated or __tests__/ (future)
```

Mirror backend paths: `cellxp/domain/coords.py` → `tests/unit/test_coordinate_validation.py`.

## Pytest configuration

Root config: `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src/backend"]`). Add a root
`tests/conftest.py` for shared fixtures when implementing.

### Markers (register in `pyproject.toml`)

| Marker | Tier | Default `make test` |
|---|---|---|
| `unit` | T1 | included |
| `integration` | T2 | included |
| `contract` | T3 | included |
| `e2e` | T4 | included (smoke); full e2e may use `slow` |
| `slow` | T4/T5/T6 | excluded locally; nightly CI |
| `browser` | T5 | excluded; run via Playwright |
| `eval` | T6 | excluded; `make eval` |
| `gpu`, `live` | T7 | excluded |

Example registration:

```toml
[tool.pytest.ini_options]
markers = [
  "unit: T1 fast deterministic tests",
  "integration: T2 graph and service integration",
  "contract: T3 OpenAPI and client compatibility",
  "e2e: T4 backend end-to-end",
  "slow: exceeds PR time budget",
  "eval: T6 golden-query evals",
  "gpu: requires GPU",
  "live: calls real external models",
]
```

Default PR-local run:

```bash
make test                    # T1–T4 smoke (exclude slow, live, gpu, eval)
pytest -m unit               # fastest loop
pytest tests/unit/test_coordinate_validation.py -k edge
```

## Writing T1 — unit tests

**Do**

- Test pure functions and node handlers as `(state_slice) -> delta` with minimal fixtures.
- Table-drive coordinate edge cases (origin wrap, minus strand, cross-contig) per `coordinate_systems.md`.
- Assert audit/provenance payloads contain **no secrets** and no raw upload bytes.
- Use `tests/fixtures/` for stable inputs; keep fixtures small and licensed.

**Don't**

- Call Ollama, Postgres, or external model APIs in unit tests.
- Assert on full LLM prose; stub structured outputs instead.

Example pattern (node):

```python
def test_risk_classifier_blocks_actionable_without_review():
    state = make_state(intent="design_crispr_guides", session_type="genome_editing")
    delta = risk_classifier_node(state)
    assert delta["review_required"] is True
```

## Writing T2 — integration tests

**Do**

- Compile the supervisor (or subgraph) with an **in-memory checkpointer** for speed.
- Stub LLM via injected fake returning schema-valid JSON (see `langchain.md`).
- Stub services via the service registry / dependency overrides (`test_service_registry.py` pattern).
- Cover: safety block, pause/resume, review gate, partial failure (`NFR-6`), task-selector re-entry.

**Don't**

- Depend on test ordering; each test builds its own graph session.

Reference: `tests/integration/test_crispr_gate.py` (enforce 100% gate coverage per actionable cap).

## Writing T3 — contract tests

**Do**

- Export OpenAPI from `cellxp.api.main:app` and diff against a committed snapshot in
  `tests/contract/openapi.snapshot.json` (fail on accidental breaking changes).
- Validate example SSE event sequences against `specs/interface/streaming_protocol.md`.
- Run TS client generation in CI:

```bash
# illustrative — wire into tests/contract/ when implementing
openapi-generator-cli generate -i openapi.json -g typescript-fetch -o /tmp/cellxp-client
cd src/frontend && pnpm exec tsc --noEmit
```

## Writing T4 — backend e2e

**Do**

- Start dependencies via `docker compose` profile `test` or Testcontainers (Postgres, Redis, MinIO).
- Use `httpx.AsyncClient` against the running ASGI app or `uvicorn` subprocess.
- Mock LLM and foundation models with recorded fixtures (`tests/fixtures/alphagenome_response.json`).
- Test: `POST /sessions` → `POST /runs` → SSE until terminal state → `GET /artifacts/{id}`.

**Don't**

- Run full e2e on every file save; mark long scenarios `@pytest.mark.slow`.

## Writing T5 — browser (Playwright)

**Location:** `tests/browser/` with `playwright.config.ts` at repo root (or `tests/browser/`).

**Do**

- Run against `pnpm dev` + `make dev-api` or a compose `test` stack; use `webServer` in config to
  start both.
- Prefer **role- and text-based selectors**; `data-testid` only for unstable scientific widgets.
- One spec per journey: `chat-stream.spec.ts`, `clarification-resume.spec.ts`,
  `artifact-genome-track.spec.ts`.
- Attach **axe** scan on chat shell and workspace (`@axe-core/playwright`) for `NFR-9` smoke.
- Record HAR or route mocks for SSE if flakiness appears; prefer real SSE against mocked backend.

**Don't**

- Screenshot-compare model output plots (non-deterministic).
- Run browser tests in default `make test`; use `make test-browser` or nightly CI.

Example `playwright.config.ts` sketch:

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/browser",
  use: { baseURL: process.env.CELLXP_WEB_URL ?? "http://localhost:3000" },
  webServer: [
    { command: "make dev-api", url: "http://localhost:8000/health", reuseExistingServer: true },
    { command: "cd src/frontend && pnpm dev", url: "http://localhost:3000", reuseExistingServer: true },
  ],
});
```

## Writing T6 — evals

Golden queries: JSONL in `evals/golden_queries/<domain>.jsonl`. Each line: `query`, `session_type`,
`expected_capabilities`, `fixture_refs`, `rubric_refs`.

Run (when implemented):

```bash
make eval                    # T6 subset for dev
CELLXP_EVAL_FULL=1 make eval # nightly-equivalent
```

Wire LangSmith datasets per `langsmith.md` for traceability; eval failures block **release**, not
every PR (`TST-8`).

## Fixtures and mocking

| Dependency | Unit (T1) | Integration (T2) | E2E (T4) |
|---|---|---|---|
| LLM | stub structured output | fake provider | recorded responses |
| AlphaGenome / Boltz / … | N/A | fixture JSON | fixture or T7 live |
| Postgres | N/A | in-memory or Testcontainers | compose |
| Redis / queue | N/A | fakeredis | compose |
| Object store | tmp path | `file://` temp dir | MinIO or tmp |

Recorded LLM responses: store **structured** tool-call payloads, not full chat logs with PII.

## Frontend unit tests (Vitest)

When adding React logic (SSE client, clarification card, artifact registry):

- Colocate `*.test.tsx` or use `src/frontend/__tests__/`.
- Mock transport, not domain math — coordinate/scientific transforms stay in backend tests (`API-10`
  boundary in `api_contracts.md` §10).
- Run: `cd src/frontend && pnpm test`.

## Make targets (target state)

Add to `Makefile` as tiers land:

```makefile
test:
	PYTHONPATH=$(PYTHONPATH) pytest -m "not slow and not live and not gpu and not eval"

test-integration:
	PYTHONPATH=$(PYTHONPATH) pytest -m integration

test-e2e:
	PYTHONPATH=$(PYTHONPATH) pytest -m "e2e and not slow"

test-e2e-full:
	PYTHONPATH=$(PYTHONPATH) pytest -m e2e

test-browser:
	pnpm exec playwright test

eval:
	PYTHONPATH=$(PYTHONPATH) python -m evals.run_evals

test-live:
	PYTHONPATH=$(PYTHONPATH) pytest -m "live or gpu" --run-live
```

Until markers are registered, `make test` runs all of `tests/` (current behavior).

Deterministic golden-result shape gates can run against recorded JSONL snapshots without an LLM
judge or live model access:

```bash
python evals/run_evals.py evaluate /path/to/results.jsonl --output /tmp/gate-report.json
```

Each result record contains `query_id` and `snapshot`. This checks required artifacts, evidence
sources, concrete model identity, review/clarification/refusal behavior, and composed capability
order. Biological correctness and prose-quality rubric scoring remain separate T6 review signals.

## CI workflows (mapping)

| Workflow | Tiers | Notes |
|---|---|---|
| `.github/workflows/ci.yml` | T0, T1, T2, T3, T4 smoke | every PR |
| `evals.yml` (extend) | T6 | nightly + manual |
| future `browser.yml` | T5 | nightly |
| future `live-models.yml` | T7 | weekly, `workflow_dispatch` |

Use path filters (`paths:` / `paths-ignore:`) per `testing_strategy.md` §5.3 when splitting jobs.

## Checklist — new capability

1. T1: I/O transforms + coordinate fixtures (`CONTRIBUTING.md` §2).
2. T2: subgraph smoke + review gate if actionable.
3. T3: new routes in OpenAPI snapshot if API surface changes.
4. T4: one HTTP path through the capability (mocked model).
5. T5: artifact renders in workspace (if user-visible).
6. T6: ≥3 golden queries + rubric cases in `evals/golden_queries/`.
7. Update `testing_strategy.md` §5.3 path table if new top-level service dir.

## Don't

- Don't commit secrets, real VCFs with patient data, or API keys in fixtures.
- Don't make T7 live tests mandatory in PR CI.
- Don't duplicate eval rubrics in pytest asserts — use T6 for LLM quality, T1/T2 for hard gates.
- Don't skip changelog when adding a new test tier or CI job (`.agents/guidelines/changelog-guidelines.md`).

## Related

`specs/evaluation/testing_strategy.md` · `langgraph.md` §Testing · `langsmith.md` ·
`interactive-visualization.md` (artifact renderer tests) · `CONTRIBUTING.md` §9.
