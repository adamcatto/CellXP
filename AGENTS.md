# AGENTS.md

Cross-agent entry point (Claude, Cursor, Codex, Gemini, …). Kept deliberately tiny so it's cheap to
auto-load at session start.

**First action for a new session:** read **`.agents/onboarding.md`** — the repo map + reading
protocol. Then read only the docs your task needs.

## 30-second orientation

- **What:** CellXP — an agentic genomics copilot (any organism; DNA/RNA + proteins +
 metabolites). Mature harness → CellXP skill/policy kernel → biological services/models
 (AlphaGenome, Evo 2, ESMFold, Boltz-2). Qwen Code is the first harness-adapter target; LangGraph is
 a compatibility workflow during migration. FastAPI + Next.js/CopilotKit; local-first reasoning.
- **Phase:** **spec-first, pre-implementation.** `specs/` and `documentation/` are the source of
  truth; most of `src/` is scaffold/stubs. Trust specs over code for intent.
- **Must-reads:** `specs/product/mission.md` → `documentation/explanation/architecture_overview.md`.
- **Conventions:** specs = what/why (normative); `.agents/guidelines/` = how-to. Stable IDs
  (`FR-*`/`NFR-*`/`CR-*`). Update `CHANGELOG.md` per `.agents/guidelines/changelog-guidelines.md`.
  Extension points in `CONTRIBUTING.md`.
- **Pull requests:** keep the title/body current and highly descriptive: motivation, architecture,
  review guide, screenshots/recordings where useful, exact test results, interpretation, limitations,
  and documentation impact. Follow `.agents/guidelines/pull-request-guidelines.md`.

Everything else (full repo map, "where do I put X", token tips) is in `.agents/onboarding.md`.
