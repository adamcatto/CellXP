# Task & Orchestration Patterns

> Status: Draft v0.1. A cookbook of **how the agent composes external models and services to solve
> tasks** — from atomic capabilities to multi-scale, systems-level analyses. Each pattern is a
> reusable recipe the planner/supervisor can instantiate (`architecture_overview.md` §5–§5.1).
> Models referenced here are defined in `documentation/reference/external_models_and_services.md`
> (section numbers cited as *catalog §N*). This doc is explanatory; the binding capability contracts
> live in `specs/product/product_requirements.md` and the per-service specs.

## 0. The shape of a task: one building block, three kinds of task

Work in CellXP is described at two granularities: a **building-block layer** (steps) and
a **task layer** (what the user asks for). Tasks come in three kinds.

### 0.1 Building block — the *step* (primitive operation)

A **step** is the smallest unit of work: a single tool/model/data call or deterministic transform —
e.g. *extract genomic coordinates for a variant*, *normalize an allele*, *fetch genomic context*,
*call AlphaGenome*, *parse/interpret model outputs*, *render an artifact*. Steps are not user-facing
on their own; each is individually recorded in the run trace (`FR-24`). Steps carry a **weight**:

- **Light steps** — fast, deterministic, cheap: coordinate extraction, normalization, lookups,
  formatting. Run inline.
- **Heavy steps** — slow/expensive/GPU: model inference, genome-wide scans, search/optimization. Run
  as async jobs (`architecture_overview.md` §7).

This is the key observation that motivates the taxonomy: even the *simplest* user task is usually a
**small (light) step plus a large (heavy) step** — see the atomic example below.

### 0.2 The three kinds of task

| Kind | What it is | Who plans it | Determinism | Example | Maps to |
|---|---|---|---|---|---|
| **Atomic** | One capability/subgraph; a short, *fixed* pipeline of steps (typically light prep + heavy core + interpretation) | Pipeline is predefined by the capability | Fully deterministic structure | "Predict this variant's effect" | `FR-13..21` |
| **Macro** | A *named, reusable, parameterized* recipe bundling several atomic tasks (and steps) into one invokable unit with a pre-baked plan | Plan is curated/recorded ahead of time; agent just fills parameters | Deterministic structure, may allow small adaptations | "Interpret-noncoding-variant" = variant effect + nearest-gene/eQTL + literature corroboration + report | composed of `FR-*`; selected by routing |
| **Composed / systems-level** | An *open-ended*, dynamically planned, possibly looping/branching workflow across many capabilities and scales | Agent plans on the fly per query | Adaptive (plan generated per run) | inverse edit design, variant→GRN, strain engineering | `FR-5/6`, `FR-18c/18d`, patterns §2–§6 |

**1) Atomic task.** Maps to a single capability. Internally it is still multi-step. *Example —
variant effect prediction:* a **small/light** sub-step (resolve the variant → genomic coordinates →
pull genomic context) followed by a **large/heavy** sub-step (orchestrate the AlphaGenome call →
extract and interpret the output deltas → emit an artifact). One capability, one fixed internal
pipeline, but heterogeneous step weights.

**2) Macro.** A macro is to a workflow what an editor macro is to keystrokes: a **recorded,
replayable, parameterized** sequence — here, of atomic tasks/steps — invoked as a unit. The agent
*recognizes or is asked for* a macro and runs its **pre-defined recipe** instead of planning from
scratch. Macros buy **speed** (skip planning), **reproducibility** (the plan is fixed), and
**evaluability** (golden workflows). They live in a macro registry and can be **product-curated** or
**user-saved** (run something good once → save the run as a macro). Macros sit between atomic and
composed: more than one capability, but a curated fixed plan rather than free-form planning.

**3) Composed / systems-level task.** Open-ended work the agent **plans dynamically**: chaining *and
looping over* models across scales (sequence → molecule → network → phenotype). This is where
orchestration earns its keep — inverse edit design, variant→network impact, metabolic
reconstruction, strain engineering — realized as multi-subtask runs with intermediate artifacts in
shared state.

### 0.3 How the layers relate

```
steps (light/heavy)  ──compose──▶  atomic tasks  ──┬─ fixed plan ─▶  macros
                                                    └─ dynamic plan ▶  composed / systems-level
```

- Steps compose into atomic tasks; atomic tasks compose into **either** macros (fixed plan) **or**
  composed tasks (dynamic plan).
- The line between a **macro** and a **composed task** is *who plans and how fixed the plan is*:
  a macro is a curated/recorded recipe (deterministic); a composed task is planned on the fly
  (adaptive).
- **Promotion path:** a composed task that gets run often and whose recipe stabilizes can be
  **promoted to a macro** (and seeded into evals as a golden workflow). Conversely, a macro that no
  longer fits a query falls back to dynamic composed planning.
- The planner/router uses this taxonomy to decide *how much to plan*: match-a-macro → execute recipe;
  single capability → run atomic pipeline; otherwise → compose a plan. (Routing/selection contract:
  `specs/agent/routing_policy.md` + `tool_use_policy.md`, to be written.)

**Pattern template.** Each pattern below is written at the composed/systems level and gives:
*Goal · Inputs · Recipe (ordered model/service steps) · Outputs · Organism notes · Caveats · Gating.*
Macros are, in effect, these recipes (or atomic subsets) frozen and named.

---

## 1. Organism-appropriate model selection (read this first)

Composed tasks routinely span organisms, and **model applicability is not uniform**:

- **AlphaGenome** and most assay/tissue-resolved regulatory models are trained on **mammalian**
  (human/mouse) data. They are the right oracle for human/mouse regulatory and variant-effect
  questions, but MUST NOT be applied naively to bacteria.
- **Evo 2** is **cross-species, including prokaryotes**, and is the default sequence oracle for
  bacterial/archaeal sequence and variant scoring, generative proposals, and embeddings.
- For bacteria, **function/structure models** (ESMFold, Boltz-2, ESM-2 zero-shot, CLEAN for EC,
  AlphaMissense for mammalian missense only) and **genome-scale metabolic models** (GEMs) carry much
  of the load, because mammalian-trained regulatory heads do not transfer.

The entity_resolver/planner records organism + assembly early (`FR-11`) and the selection step picks
the organism-valid model per `specs/agent/tool_use_policy.md`. Every composed pattern below inherits
this rule.

---

## 2. Variant → gene regulatory network (GRN) impact

**Goal.** Predict how a (usually non-coding/regulatory) variant perturbs a gene regulatory network:
which TF→target edges change, and which downstream genes/modules are dysregulated.

**Inputs.** Variant(s) (rsID/HGVS/interval) + organism + assembly; optionally a cell type/tissue;
optionally expression data to anchor the network.

**Recipe.**
1. **Local regulatory effect** — score the variant's effect on TF binding / chromatin accessibility
   / expression with **AlphaGenome** (mammalian) or **Evo 2** (other species); base-resolution
   footprint deltas via **ChromBPNet** (catalog §1/§2/§6). Identify which motifs/TFs gain or lose
   binding (**FIMO + JASPAR**).
2. **Edge mapping** — link the affected regulatory element to its target gene(s): proximity + gene
   models (annotation, catalog §7) and enhancer–gene linking (**ABC / activity-by-contact**,
   catalog §12). This yields the perturbed TF→target edges and the magnitude of change.
3. **Network context** — place the edges in a GRN: either a curated/known network or one inferred
   from expression (**GRNBoost2/GENIE3**, **SCENIC**; catalog §14).
4. **Propagation** — propagate the edge perturbation through the network (graph algorithms) to rank
   downstream-affected genes/modules and implicated pathways (Reactome/GO, catalog §17).
5. **Synthesis** — report perturbed sub-network as an interactive graph artifact + cited
   interpretation with confidence.

**Outputs.** Δ-edge list, ranked downstream genes, affected modules/pathways, network artifact.
**Organism notes.** Mammalian → AlphaGenome oracle; non-mammalian → Evo 2 + motif/footprint.
**Caveats.** Edge changes are predictions, not measurements; propagation assumes the network
topology is approximately correct — surface both as confidence/limitations (`FR-23`).
**Gating.** Analysis (not actionable) → no gate; if it feeds an edit proposal, gate the edit.

---

## 3. Variant → metabolism in a bacterial strain

**Goal.** Predict how a sequence variant in a bacterial strain (e.g. *G. oxydans*) changes
metabolism — flux redistribution, growth, or yield of a target metabolite.

**Inputs.** Variant(s) + strain genome/assembly (bacterial, circular-aware); a target phenotype
(growth, a product flux); optionally media/conditions.

**Recipe.**
1. **Classify the variant's locus** — coding vs regulatory/intergenic (annotation: **Pyrodigal /
   Bakta**, catalog §7).
2. **Coding variant → enzyme effect** — predict functional/structural/stability impact: **ESM-2**
   zero-shot scoring, **ESMFold/Boltz-2** for structural consequence, **CLEAN** to confirm/assign EC
   (catalog §3/§15). Translate to an effect on the corresponding **reaction** (impair/abolish/retune).
3. **Regulatory variant → expression effect** — score with **Evo 2** (prokaryote-capable) to estimate
   up/down-regulation of the affected gene(s)/operon; translate to an enzyme-abundance change.
4. **Map onto a genome-scale metabolic model (GEM)** — locate the affected reaction(s) in the
   strain's GEM (see Pattern §4 to build one); encode the effect as modified reaction bounds, a
   knockout, or an expression-derived flux constraint.
5. **Simulate** — run **FBA/FVA** (**COBRApy**, catalog §14) under the specified media to predict
   growth and the target-metabolite flux; compare wild-type vs variant.
6. **Synthesis** — report predicted phenotype shift, the responsible reaction(s)/pathway, and
   confidence; flux-map and pathway artifacts.

**Outputs.** WT-vs-variant flux deltas, growth/yield prediction, implicated reactions/pathways.
**Organism notes.** This is a prokaryote pattern: **no AlphaGenome**; Evo 2 + function/structure +
GEM. Respect circular coordinates and operon structure.
**Caveats.** GEM coverage/quality bounds accuracy; sequence→expression and enzyme→kinetics mappings
are approximate (FBA is steady-state, parameter-light). State assumptions explicitly.
**Gating.** Analysis → no gate; engineering recommendations → gated (Pattern §6).

---

## 4. Metabolic network inference / reconstruction (build a GEM from a genome)

**Goal.** Construct a draft genome-scale metabolic model for an organism (often a non-model
bacterium) to enable the analyses above.

**Inputs.** Genome assembly (+ optional proteome), target organism, optional curated reference.

**Recipe.**
1. **Gene calling + annotation** — **Pyrodigal** (ORFs) → **Bakta** (annotation) (catalog §7).
2. **Functional/EC assignment** — **eggNOG-mapper / InterProScan** + **CLEAN** for enzyme EC numbers
   (catalog §7/§15); resolve gene→enzyme→reaction associations.
3. **Draft reconstruction** — assemble reactions into a GEM via **CarveMe / ModelSEED** (catalog §14),
   seeded from the EC/ortholog assignments.
4. **Gap-filling + QC** — gap-fill to enable biomass production on defined media; sanity-check mass/
   charge balance and blocked reactions.
5. **Validation** — compare predicted growth/essentiality to any known phenotypes; flag low-confidence
   reactions.
6. **Deliver** — the GEM as a reusable artifact (SBML) + a reconstruction report.

**Outputs.** Draft GEM (SBML), annotation evidence per reaction, QC/validation report.
**Caveats.** Automated reconstructions are drafts; gap-fills and promiscuous EC calls are the main
error sources — provenance per reaction is essential (`FR-22/24`). Curation is iterative.
**Gating.** Analysis artifact; not actionable on its own.

---

## 5. Gene regulatory network inference (build a GRN)

**Goal.** Infer a GRN to support Pattern §2 when no curated network exists.

**Inputs.** Expression matrix (bulk or single-cell) ± a TF list ± sequence/motif priors.

**Recipe.**
1. **Co-expression edges** — **GRNBoost2/GENIE3** (catalog §14) for TF→target candidate edges.
2. **Motif pruning** — retain edges with supporting TF-motif evidence in target regulatory regions
   (**SCENIC** regulons; FIMO + JASPAR; for sequence-grounded priors, AlphaGenome/Evo 2 predicted
   binding) (catalog §1/§6/§14).
3. **(Single-cell)** — optionally derive cell-type-specific regulons (SCENIC; scVI/scGPT embeddings,
   catalog §18, exploratory).
4. **Deliver** — GRN artifact with edge weights + evidence.

**Outputs.** GRN (nodes/edges + weights + evidence), per-edge provenance.
**Caveats.** Correlation ≠ causation; report inference method + confidence; networks are
condition-specific.

---

## 6. Strain / pathway engineering toward a production goal (flagship, composed)

**Goal.** Given a production objective (e.g. "increase yield of product P in *G. oxydans* under
aerobic conditions"), propose genetic interventions that achieve it — uniting inverse edit design
(catalog §11) with metabolic modeling.

**Inputs.** Objective metabolite/flux + strain GEM (Pattern §4) + organism/assembly + constraints
(media, essential genes, editing system).

**Recipe.**
1. **In-silico target identification** — use GEM strain-design algorithms (FBA/FVA, knockout/
   amplification searches such as OptKnock-style analyses in **COBRApy**) to nominate reactions to
   delete/up/down-regulate for the objective.
2. **Map reactions → genes → edits** — translate each metabolic target to a gene and a realizable
   **edit** (knockout, promoter swap for expression tuning, etc.).
3. **Inverse edit design per target** — for each edit, run the **model-guided edit design** loop
   (catalog §11; `FR-18c`): propose edits, forward-score effect (Evo 2 for expression/regulatory,
   function/structure models for enzymes), penalize **off-target + collateral** (Cas-OFFinder/CFD),
   optimize.
4. **Re-simulate the combined design** — feed the predicted expression/function changes back into
   the GEM and re-run FBA to estimate the *net* phenotype of the full intervention set.
5. **Rank + assess** — rank candidate intervention sets by predicted yield, feasibility, off-target
   burden, and collateral metabolic disruption.
6. **Propose experiments** — emit a design package (edits + sequences + design files) and **suggest
   validation experiments**, all **behind the human-review gate**.

**Outputs.** Ranked intervention sets, per-edit off-target/feasibility, predicted yield, design
files, suggested experiments.
**Organism notes.** Canonical *G. oxydans* climate-biotech use-case (`mission.md` §4).
**Caveats.** Compounding model error across the chain — propagate uncertainty (see §7) and present as
hypotheses to test, never as guarantees.
**Gating.** Actionable → **review-gated** (`FR-25/26`, ADR-0005).

---

## 7. Cross-cutting concerns for composed tasks

- **Uncertainty propagation.** Each step carries confidence; composed outputs MUST reflect compounded
  uncertainty (worst-case/limiting step highlighted), not just the last step's confidence
  (`FR-23`, `evidence_and_confidence.md`).
- **Provenance across the chain.** Every model call in the chain is recorded with version/params so
  the whole composed run is reproducible (`FR-24`, `FR-30/32`).
- **Intermediate artifacts.** Each stage emits an inspectable artifact (deltas, network, GEM, flux
  map) so users can audit/branch mid-chain (`FR-27..29`).
- **Graceful degradation.** If one stage fails (e.g. no GEM available), return partial results +
  a clear gap rather than aborting the run (`NFR-6`).
- **Human review.** Any chain that terminates in actionable biology routes through the gate; the
  *analysis* portions remain ungated.

## 8. Pattern → requirement / capability map

| Pattern | Primary FR(s) | Key catalog sections |
|---|---|---|
| §2 Variant → GRN impact | FR-13, FR-17, FR-18d | §1, §2, §6, §14, §17 |
| §3 Variant → metabolism (bacterial) | FR-13, FR-18b, FR-18d | §1, §3, §7, §14, §15 |
| §4 Metabolic network inference | FR-18b, FR-18d | §7, §14, §15 |
| §5 GRN inference | FR-18d | §1, §6, §14, §18 |
| §6 Strain/pathway engineering | FR-18c, FR-18b, FR-18d, FR-15 | §1, §10, §11, §14 |

## 9. Related docs

- Orchestration mechanics: `architecture_overview.md` §5–§5.1
- Model inventory: `documentation/reference/external_models_and_services.md`
- Capability contracts: `specs/product/product_requirements.md`
- Inverse design detail (to be written): `specs/biology/inverse_edit_design.md`
- Tool selection policy: `specs/agent/tool_use_policy.md`
