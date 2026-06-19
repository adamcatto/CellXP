# Agent Nodes

Per-node specifications for the **top-level** graph nodes. Each file details one node's contract:
what state it reads/writes, its behavior, errors, and (for LLM-backed nodes) its prompt asset.

Parent specs: `specs/agent/graph_spec.md` §4 (node catalog), `specs/agent/state_schema.md` (state
contract). Implementation: `src/backend/cellxp/agent/nodes/*`, prompts in
`agent/prompts/*`.

## Node index (execution order)

| # | Node | File | Kind | One-liner |
|---|---|---|---|---|
| 1 | input_normalizer | `input_normalizer.md` | deterministic | raw inputs → normalized inputs |
| 2 | intent_classifier | `intent_classifier.md` | LLM | classify intent |
| 3 | risk_classifier | `risk_classifier.md` | LLM+rules | early safety classification |
| 4 | entity_resolver | `entity_resolver.md` | LLM+tools | resolve bio entities; ask if ambiguous |
| 5 | planner | `planner.md` | LLM | choose macro / atomic / composed plan |
| 6 | task_selector | `task_selector.md` | deterministic | dispatch next ready subtask (loop hub) |
| 7 | evidence_integrator | `evidence_integrator.md` | deterministic+LLM | normalize/reconcile evidence |
| 8 | human_review_gate | `human_review_gate.md` | gate | actionable-biology review pause |
| 9 | critic | `critic.md` | LLM | self-check before report |
| 10 | report_generator | `report_generator.md` | LLM | synthesize cited answer |

Conventions: every node is a pure reduction into `AgentState`; nodes that may run concurrently write
only append/merge-by-id fields (`state_schema.md` §16). Control flow between nodes:
`specs/agent/control-flow/`.
