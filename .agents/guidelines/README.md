# Engineering Guidelines

Practical, code-level guidelines for building CellXP. These are **how-to-implement**
companions to the **what/why** specs in `specs/` and `documentation/explanation/`. When a spec and a
guideline disagree on intent, the spec wins; when they disagree on mechanics, fix the guideline.

| Guideline | Use when |
|---|---|
| `langgraph.md` | maintaining the LangGraph compatibility workflow, state, interrupts, checkpointing |
| `langchain.md` | model abstraction, structured outputs, tools, messages, the LLM service |
| `deepagents.md` | evaluating/maintaining the optional deepagents compatibility path |
| `langsmith.md` | tracing, evals, datasets, the post-training flywheel |
| `interactive-visualization.md` | building artifacts/visualizations (genome tracks, structures, plots) |
| `feature-documentation.md` | synchronizing specs, docs, planning, tests, and changelog for feature changes |
| `changelog-guidelines.md` | maintaining `CHANGELOG.md` |
| `atomic-commits.md` | staging and committing only the files you touched (path-scoped commits) |
| `pull-request-guidelines.md` | writing evidence-rich PR titles/bodies with visuals, results, interpretation, and caveats |
| `testing.md` | writing and running the test pyramid (pytest, Playwright, evals, CI triggers) |
| `setup-scripts.md` | maintaining bootstrap, dependency initialization, and model downloads |

Stack relationship (see ADR-0008): the **CellXP skill/policy kernel** is stable;
**HarnessAdapter** implementations (Qwen Code first) sit above it; LangGraph/deepagents are
compatibility/comparison paths. **LangSmith** observability/evals cuts across adapters.
