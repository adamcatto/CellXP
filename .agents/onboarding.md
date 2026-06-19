# Agent Onboarding — start here

Canonical "get up to speed fast" guide for **any** coding agent (Claude, Cursor, Codex, Gemini, …)
starting a session in this repo. It's a **map, not a manual**: read this, then read *only* the few
docs your task needs. Goal: avoid scanning the whole tree at session start.

## 1. What this repo is (10-second version)

**CellXP** — an agentic copilot for genomics (any organism: human → mouse → bacteria),
covering DNA/RNA + proteins + metabolites. A **LangGraph supervisor** orchestrates capability
subgraphs (variant effect, GWAS, CRISPR, annotation, binding, structure, DNA origami, RAG,
visualization) over external foundation models (AlphaGenome, Evo 2, ESMFold, Boltz-2, …). Backend =
FastAPI/Python; frontend = Next.js; reasoning LLM = local-first via Ollama (default `gemma4:4b`).

## 2. Project phase — READ THIS

This repo is **spec-first and pre-implementation**. The `specs/` and `documentation/` trees are the
**source of truth**; most of `src/` is **scaffold/stubs** (real directory layout, mostly empty
implementations). So:

- For *intent / requirements / design* → trust `specs/` and `documentation/`, **not** the code.
- Don't assume a function is implemented because the file exists. Check before relying on it.
- When you implement something, make the code conform to the spec; if the spec is wrong, fix the spec.

## 3. Minimal reading protocol (do this, in order)

1. **This file** (you're here).
2. `specs/product/mission.md` — what we're building and why (the one must-read).
3. `documentation/explanation/architecture_overview.md` — the tech stack + system shape.
4. **Then stop and read task-targeted docs only** using the map in §4. Don't pre-read everything.

For most tasks that's ~3 files + 1–3 task-specific ones. Resist reading whole folders.

## 4. Repo map (where to look for what)

Every folder below has a `README.md` index where noted — **read the README before the folder's files.**

| Area | Path | What's there |
|---|---|---|
| Product specs | `specs/product/` | `mission`, `product_requirements` (FR-*/NFR-*/CR-*), `personas`, `user_stories`, `success_metrics` |
| Agent specs | `specs/agent/` | `state_schema`, `graph_spec`, routing/tool-use/evidence/human-review policies, `session_types`, `harness_and_context_engineering` |
| ↳ nodes | `specs/agent/nodes/` (README) | per-node specs (input_normalizer, planner, task_selector, …) |
| ↳ capability subgraphs | `specs/agent/capability-subgraphs/` (README) | per-capability subgraph specs |
| ↳ control flow | `specs/agent/control-flow/` (README) | run lifecycle, pause/resume, concurrency, replanning/budget |
| Biology methods | `specs/biology/` (README) | per-capability I/O/models/transforms; `supported_species`, `supported_assays` |
| Services | `specs/services/` | per-service contracts (alphagenome, gwas, crispr, structure, binding, rag, llm, reference, visualization) |
| Interface | `specs/interface/` | `api_contracts`, `chat_interface`, `streaming_protocol`, `genome_browser`, `workspace_interface`, `artifact_model` |
| Data | `specs/data/` | relational/vector/object storage, provenance, audit log |
| Evaluation | `specs/evaluation/` | testing strategy, eval plan, golden sets, rubrics, regression tests |
| Training | `specs/training/` | `post_training` (SFT/DPO/RLVR) — offline only |
| Planning | `specs/planning/` | `roadmap` (near-term, committed), `future-additions` (backlog), `milestones`, `open_questions`, `risks` |
| Explanations (why) | `documentation/explanation/` | architecture, multi-agent, harness/context eng., safety, evidence/confidence, coordinate systems, task patterns, why_langgraph |
| Decisions | `documentation/adr/` | architectural decision records (numbered) |
| How-to (implement) | `.agents/guidelines/` (README) | langgraph, langchain, deepagents, langsmith, interactive-visualization, testing, changelog-guidelines |
| Reference | `documentation/reference/` | `external_models_and_services`, api, cli, config, env vars, service registry, db tables |
| Community notes | `documentation/community-notes/` (README) | practical caveats (e.g. AlphaGenome-not-for-bacteria) |
| Backend code | `src/backend/cellxp/` | agent/, api/, services/, domain/, storage/, jobs/, cli/, config/ (mostly stubs) |
| Frontend code | `src/frontend/` | Next.js app/, components/, lib/ (mostly stubs) |
| Tests / evals | `tests/`, `evals/` | unit/integration/e2e; golden queries + rubrics |

## 5. Conventions

- **Spec vs guideline:** `specs/` + `documentation/explanation/` = *what/why* (normative). `.agents/guidelines/` = *how to implement* (mechanics). On intent conflict, **spec wins**; on mechanics conflict, fix the guideline.
- **Requirement IDs are stable:** `FR-*` (functional), `NFR-*` (non-functional), `CR-*` (constraint), plus `HARN-*`/`CTX-*`/`PT-*`. Reference them; don't renumber casually.
- **Decisions** go in `documentation/adr/` (one per decision, numbered).
- **Planning:** committed/near-term → `specs/planning/roadmap.md`; speculative → `specs/planning/future-additions.md`. See either file's header for the promotion gate + status vocabulary.
- **Changelog:** update `CHANGELOG.md` for notable changes, following `.agents/guidelines/changelog-guidelines.md` (Keep a Changelog; edit the `[Unreleased]` section).
- **Commits:** keep commits atomic — only the files you touched, with explicit paths; see `.agents/guidelines/atomic-commits.md`.
- **Contributions / extension points** (new species, strain, assay, capability, model, harness, macro): `CONTRIBUTING.md`.

## 6. "Where do I put / find X?" quick table

| I want to… | Go to |
|---|---|
| understand a capability's biology I/O | `specs/biology/<capability>.md` |
| change agent control flow / a node | `specs/agent/` (+ `nodes/`, `control-flow/`) |
| add/adjust a model or external service | `documentation/reference/external_models_and_services.md` + `specs/services/` |
| add a species / strain / assay | `specs/biology/supported_{species,assays}.md` + `CONTRIBUTING.md` |
| see/queue future work | `specs/planning/{roadmap,future-additions}.md` |
| know how to implement w/ the stack | `.agents/guidelines/` |
| record a gotcha for others | `documentation/community-notes/` |

## 7. Token-efficiency tips

- Prefer this map + folder `README.md`s over recursive reads.
- Use search (grep) for specific symbols/IDs (e.g. `FR-13`, a node name) instead of reading files whole.
- Read a doc's header/§1 first; many specs front-load scope + related-links.
- Don't read `src/` to learn intent — it's stubs; read the spec instead.

## 8. Before you finish a task

- Make code/specs internally consistent (update cross-references and IDs).
- Update `CHANGELOG.md` if the change is notable.
- If you hit a non-obvious caveat, drop a `documentation/community-notes/` entry.
