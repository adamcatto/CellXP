# ADR-0001 — Use a unified `src/` layout (backend + frontend in one repo)

- **Status:** Accepted (v0.1)
- **Date:** initial repo bootstrap
- **Related:** `documentation/explanation/architecture_overview.md` §2 (packaging), `pyproject.toml`, `package.json`

## Context

CellXP has two first-class implementations that ship together: a Python FastAPI + LangGraph
backend and a TypeScript Next.js web client (with a future native macOS shell). The two are
co-evolved — a change to a typed payload in the backend frequently requires a matching change
in the generated TypeScript client and the rendering pane that consumes it. The product is
also expected to ship as a coherent application, not as independent backend/frontend services
with their own release cadences.

Three common layouts were on the table:

1. **Two repos**, one per stack, with the TypeScript client consuming a separately published
   OpenAPI document.
2. **A monorepo with separate top-level packages** (`/backend/`, `/frontend/`), each with its
   own tool config rooted at the package directory.
3. **A unified `src/` layout** with both stacks under `src/backend/` and `src/frontend/`,
   sharing the repo root for CI, linting config, ADRs, specs, and infra manifests.

## Decision

Use **option 3**: one repository with a unified `src/` directory containing `src/backend/`
(Python package `cellxp`) and `src/frontend/` (TypeScript workspace). The repo root carries
`pyproject.toml`, `package.json`, `docker-compose.yml`, `Makefile`, `specs/`, `documentation/`,
`infra/`, `evals/`, `tests/`, and the rest of the cross-cutting tooling.

Concretely:

- `pyproject.toml` declares `[tool.setuptools.packages.find] where = ["src/backend"]` so the
  installable Python package is `cellxp` from `src/backend/cellxp/...`.
- `package.json` at the root is a thin pnpm workspace wrapper that delegates `dev`/`build`/`lint`
  into `src/frontend/`.
- `pythonpath = ["src/backend"]` in `[tool.pytest.ini_options]` makes the package importable
  in tests without an install step during local iteration.
- Single CI pipeline runs Python tests, TypeScript build, and (eventually) e2e tests in one
  workflow — guaranteeing matched versions ship together.

## Consequences

**Positive**

- Cross-cutting changes (typed payload + generated client + pane renderer) are a single PR
  with a single review, single CI run, single revert.
- One source of truth for ADRs, specs, ops manifests, and CI. No version drift between
  "backend repo" and "frontend repo" — a tagged release is a tagged snapshot of the whole
  system.
- Generated TypeScript client from FastAPI's OpenAPI document is wired into the same CI as
  the schema it generates from; drift is caught at PR time (`API-9`).
- Onboarding is one `git clone` + `docker compose up`; new contributors do not have to
  reason about which repo touches which surface.

**Negative / accepted trade-offs**

- The repo is larger and CI is heavier per-PR than a single-stack repo would be. Mitigated by
  affected-only test selection and per-package build caches.
- Releasing the frontend independently (e.g. an emergency UI hotfix) requires care to avoid
  shipping unrelated backend changes; mitigated by the fact that the deployable build is one
  artifact bundle in regimes 1–2, and by per-component image tags in regime 3.
- New contributors who know only one stack must learn the other layout's conventions enough
  to navigate the tree; the `README.md` and `AGENTS.md` files at the root point them at the
  relevant subtree quickly.

**Out of scope (deliberately not adopted)**

- A formal monorepo manager (Nx, Turborepo, Bazel). The current scale doesn't justify the
  added complexity; we will revisit if the build graph genuinely warrants it.
- A shared "common types" package. The TypeScript client is generated from the FastAPI
  OpenAPI document; there is no second source of truth to keep in sync.

## Status notes

We will revisit this decision if (a) the macOS native shell grows enough that it warrants
its own repository for native-toolchain reasons, or (b) external consumers want the OpenAPI
client published as a standalone package on a different release cadence than the app.
