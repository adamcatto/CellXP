# inverse_design Subgraph

> Status: Implemented v0.1. Capability: `FR-18c`. Implementation:
> `agent/subgraphs/inverse_design.py`, `services/inverse_design/`.

The subgraph frames a desired effect, runs the bounded propose → forward-score → CRISPR-feasibility
loop, ranks the Pareto candidates, and emits evidence plus an actionable candidate-edit table. The
top-level supervisor always routes the result through `human_review_gate` before report generation.

Inputs require `target_effect`, locus/gene, organism, and assembly. No configured backend is an
explicit unsupported result; malformed/missing objectives fail with a typed run error.
