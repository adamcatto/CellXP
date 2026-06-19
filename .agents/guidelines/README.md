# Engineering Guidelines

Practical, code-level guidelines for building CellXP. These are **how-to-implement**
companions to the **what/why** specs in `specs/` and `documentation/explanation/`. When a spec and a
guideline disagree on intent, the spec wins; when they disagree on mechanics, fix the guideline.

| Guideline | Use when |
|---|---|
| `langgraph.md` | building the supervisor graph, nodes, subgraphs, state, interrupts, checkpointing |
| `langchain.md` | model abstraction, structured outputs, tools, messages, the LLM service |
| `deepagents.md` | sub-agents, virtual filesystem, planning, context compaction |
| `langsmith.md` | tracing, evals, datasets, the post-training flywheel |
| `interactive-visualization.md` | building artifacts/visualizations (genome tracks, structures, plots) |
| `changelog-guidelines.md` | maintaining `CHANGELOG.md` |
| `atomic-commits.md` | staging and committing only the files you touched (path-scoped commits) |
| `testing.md` | writing and running the test pyramid (pytest, Playwright, evals, CI triggers) |

Stack relationship (see `documentation/explanation/harness_and_context_engineering.md` §A4):
**LangGraph** (graph runtime) → **LangChain `create_agent`** (minimal harness) → **deepagents**
(opinionated harness) → **LangSmith** (observability/evals) cuts across all.
