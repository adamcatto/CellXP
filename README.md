# CellXP

CellXP is a full-stack, LangGraph-based genome AI copilot for regulatory variant interpretation, GWAS/QTL lookup, CRISPR guide design, sequence annotation, binding-site prediction, DNA/chromatin structure prediction, DNA origami workflows, and interactive scientific visualization.

Repository layout:

- `src/backend/cellxp/` — Python backend, FastAPI API, LangGraph agent, biological domain models, service clients, storage, jobs, CLI.
- `src/frontend/` — Next.js App Router frontend and interactive workspace.
- `specs/` — implementation-driving contracts and requirements.
- `documentation/` — human-facing tutorials, guides, reference, explanations, diagrams, ADRs.

Python distribution name: `cellxp`.
Python import package: `cellxp`.
Product/display name: `CellXP`.

## Contributing

The system is built to be extended — new capabilities/tasks, models/packages, species/strains,
assays, harnesses, artifacts, evals, and community notes/caveats. See `CONTRIBUTING.md` for what each
contribution requires and how to make it, and `.agents/guidelines/` for implementation patterns.
