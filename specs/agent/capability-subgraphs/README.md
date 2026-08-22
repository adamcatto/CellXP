# Capability Workflows (LangGraph compatibility profiles)

These files specify reusable **domain workflow contracts**. The implemented LangGraph compatibility
runtime exposes them as subgraphs; the target harness exposes bounded versions as typed
`SkillPlugin`s (`skill_plugin_contract.md`). Each file details one capability's contract: the
`Subtask`/skill input it consumes, its internal **steps**
(light prep + heavy core), the models/services it invokes, the evidence/artifacts it produces,
whether it is actionable (review-gated), and organism notes.

Parent specs: `specs/agent/skill_plugin_contract.md`, `graph_spec.md` §5 (compatibility mapping),
`specs/agent/state_schema.md`,
`specs/agent/tool_use_policy.md`. Models: `documentation/reference/external_models_and_services.md`
(cited *catalog §N*). Impl: `src/backend/cellxp/agent/subgraphs/*`. Methodology:
`specs/biology/*`. Service contracts: `specs/services/*`.

## Uniform capability contract

- **In:** the selected `Subtask` (+ relevant `normalized_inputs`/`entities`).
- **Do:** run internal steps; call services via the registry (`tool_use_policy.md`); record each step
  (`state_schema.md` §8).
- **Out:** append `evidence` + `artifacts`; set `Subtask.status` + `result_ref`.
- **Gate:** actionable subgraphs mark output `is_actionable` → `human_review_gate`.

## Subgraph index

| Subgraph | File | Actionable | Primary models/services | FR |
|---|---|---|---|---|
| variant_effect | `variant_effect.md` | no | AlphaGenome / Evo 2 (catalog §1) | FR-13 |
| gwas | `gwas.md` | no | GWAS Catalog, Open Targets, SuSiE (§9) | FR-14 |
| crispr | `crispr.md` | **yes** | guide design + off-target (§10) | FR-15 |
| inverse_design | `inverse_design.md` | **yes** | forward oracle + CRISPR feasibility (§11) | FR-18c |
| annotation | `annotation.md` | no | Bakta/Pyrodigal, AlphaGenome (§7) | FR-16 |
| binding | `binding.md` | no | AlphaGenome heads, ChromBPNet, FIMO (§6) | FR-17 |
| structure | `structure.md` | no | ESMFold, Boltz-2 (§3/§4/§5) | FR-18 |
| origami | `origami.md` | **yes** | cadnano/scadnano (§16) | FR-19 |
| rag | `rag.md` | no | PubMed, retriever (§17) | FR-20 |
| visualization | `visualization.md` | no | visualization service | FR-21 |

> Composed/systems-level work may be an internally composed subgraph (the shipped bounded
> `inverse_design` loop) or a multi-subtask plan traversing several capabilities (`task_patterns.md`
> §2–§6, `routing_policy.md` §7). Protein/metabolite/network capabilities (`FR-18a/b/d`) are realized by
> extending `structure`/`annotation`/`binding` subgraphs + future `design`/`systems` subgraphs.
