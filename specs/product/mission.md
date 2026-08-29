# Mission

> Status: Draft v0.1 — foundational spec. Downstream specs (product requirements, personas,
> services, interface) MUST stay consistent with this document. When this and a downstream spec
> conflict, this document wins until explicitly revised.

## 1. One-line mission

CellXP is an agentic copilot for genomics and molecular biology — it turns a question
about DNA, RNA, proteins, or the metabolites they produce, posed in natural language and/or as
sequence data itself (FASTA, raw nucleotide/protein sequences, variants, intervals, files), into a
grounded, reproducible, and visually legible answer, for any organism from humans to mice to bacteria
and anywhere in between.

## 2. The problem

Modern genomics is bottlenecked largely by *orchestration*. Answering even a routine
question — "is this non-coding variant likely regulatory, and in which tissue?", "design three
CRISPR guides for this locus with low off-target risk", "predict the structure of this RNA and show
me the contact map" — requires a researcher to:

- locate the right reference assembly and coordinate system,
- normalize messy inputs (rsIDs, HGVS, FASTA, gene symbols, intervals),
- pick and correctly invoke the right model or tool (AlphaGenome/Evo2, ESMFold/Boltz, GWAS
  catalogs, CRISPR scorers, origami designers),
- stitch outputs together, sanity-check them against the literature, and
- produce a figure and a defensible written conclusion.

Each step is individually tractable and collectively exhausting. The expertise is unevenly
distributed, the tools have incompatible interfaces, and the glue work is rarely reproducible. The
result is slow iteration and answers whose provenance is hard to audit.

## 3. What CellXP is

A full-stack biological agent with a chat-driven workspace, a mature pluggable harness, and
CellXP-owned typed skills/policy enforcement (ADR-0008). Input is **multimodal**:
a user can ask in natural language, drop in sequence data directly (FASTA, raw DNA/RNA/protein
sequences, rsIDs, HGVS, genomic intervals, gene symbols), upload a file (e.g. a FASTA or variant
list), or any combination — for example, paste a sequence with no prose and simply ask "what is
this?", or attach a FASTA and request a structure. The orchestrating agent classifies intent,
parses and normalizes whatever was provided, resolves biological entities, plans a sequence of
subtasks, dispatches them to specialized services, integrates the evidence, and returns:

1. a written answer with inline citations and explicit confidence,
2. one or more interactive **artifacts** (genome browser tracks, locus plots, 3D structures,
   contact maps, guide tables, origami layouts), and
3. a fully inspectable **run trace** of every tool call, input, and output.

Crucially, this is an **agentic** system, not a one-shot question-answerer. Beyond producing
artifacts it can take **actions and have side effects**: it reasons over multiple steps, decomposes
and revises its own plan, chains and *composes* artifacts (feeding one result into the next — e.g.
annotate → predict effect → design a guide → visualize, with possible loops in between), persists outputs and optionally **writes files** to
the workspace/object store (FASTA, BED/VCF, design files, reports, notebooks), proposes and
sequences **follow-up analyses**, and **suggests experiments** or next steps for the user to pursue.
The unit of work is an agent *run* that can mutate state and leave durable artifacts behind, not
merely a chat reply.

It is a copilot, not an autopilot: this autonomy is bounded. The agent reasons and proposes freely,
but anything that proposes *actionable* biology (e.g. a CRISPR edit, a primer, an origami design) —
or any consequential side effect — is routed through a human-review gate before it is presented as a
recommendation or committed.

Under the hood the agent is a **hierarchical multi-agent system** (a mature harness that plans and
routes, typed capability/workflow skills that execute through the policy kernel, and isolated
sub-agents for deep/expensive subtasks; `documentation/explanation/multi_agent_architecture.md`).
Work happens inside persistent, typed
**sessions (workspaces)** — e.g. a *variant interpretation*, *genome editing*, or *strain
optimization* session — that carry defaults, memory, and accumulated artifacts across many runs
(`specs/agent/session_types.md`). As it works, the agent **streams** its activity progressively:
intent, a collapsible view of its reasoning, live tool calls with inputs/outputs, partial results,
and artifacts that fill in as they render (`specs/interface/streaming_protocol.md`).

## 4. Scope

### In scope (the domain)

The domain centers on the **central dogma and the molecules genomes act on and produce** — DNA, RNA,
**proteins**, and **metabolites / small molecules** — together with the complexes, pathways, and
synthetic constructs built from them. Any conceivable task spanning these, including but not limited
to:

- **Variant interpretation** — regulatory/functional effect prediction for coding and non-coding
  variants (AlphaGenome, Evo2), tissue/assay-resolved deltas.
- **GWAS / QTL** — trait association lookup, fine-mapping, LD, colocalization, Open Targets-style
  evidence aggregation.
- **CRISPR design** — gRNA design, on-/off-target scoring, base editing, prime editing. Discusses tradeoffs between editing systems, e.g. Cas protein selection, site selection, and so on.
- **Model-guided edit design (inverse design)** — the *inverse* of variant interpretation: given a
  desired functional effect, search the realizable edit space to find genome edits that achieve it
  while **minimizing off-target and collateral effects**, by composing forward effect models
  (AlphaGenome/Evo2) as the objective with CRISPR/base/prime-edit design and genome-wide off-target
  analysis. Actionable → review-gated. A flagship capability for the bioengineering persona.
- **Sequence annotation** — gene models, regulatory features, motifs, ORFs, functional elements. Can use models like AlphaGenome and DeepRegFinder for genome annotation. May ask user if they have a preference for annotation method.
- **Binding-site prediction** — TF motif scanning, footprinting, occupancy deltas. AlphaGenome-based TF binding site prediction.
- **Structure prediction** — protein (ESMFold/Boltz-style), nucleic-acid and complex structure, DNA
  shape, nucleosome positioning, chromatin contact maps.
- **Protein analysis & design** — function/annotation (enzyme EC, domains, GO), structure, and
  protein/sequence/binder design (e.g. LigandMPNN, RFdiffusion), with actionable designs review-gated.
- **Metabolites & small molecules** — cheminformatics, protein–ligand binding/affinity, and
  genome-scale metabolic modeling (pathways, flux) for metabolic-engineering use-cases.
- **Networks & systems-level analysis** — inferring and reasoning over biological networks across
  scales: gene-regulatory-network (GRN) inference and how variants rewire regulatory edges; metabolic
  network reconstruction and flux analysis; and how DNA sequence variants ripple up to metabolism and
  phenotype (e.g. variant→flux→yield in a bacterial strain). Realized by composing the forward models
  above with network/metabolic tools — see `documentation/explanation/task_patterns.md`.
- **DNA origami / nanotech** — scaffold routing, staple design, constraint checking, cadnano-style
  export.
- **Literature grounding (RAG)** — retrieval and citation of primary literature and databases.
- **Visualization** — turning any of the above into interactive, exportable scientific figures.

### Biological entities & products in scope

The copilot reasons over, and produces, these classes of biological entity:

- **First-class (v1):** DNA, RNA, **proteins** (incl. peptides, enzymes, antibodies), **metabolites
  & small molecules** (substrates, products, ligands), macromolecular **complexes & interactions**
  (protein–protein, protein–DNA/RNA, protein–ligand), biological **pathways & networks** (metabolic,
  regulatory), and **synthetic constructs** (plasmids, vectors, designed parts, DNA-origami
  nanostructures).
- **Exploratory / future:** glycans (glycomics), lipids (lipidomics), and cells / cell types
  (single-cell). These are acknowledged extensions of the same machinery, gated until prioritized
  (tracked in `specs/planning/future-additions.md`).

The throughline is *genotype → molecular phenotype*: from a genome (any organism) to the RNA,
proteins, and metabolites it specifies, and the engineered constructs a researcher might build from
them.

### Organisms

Organism-agnostic by design: human, mouse, and bacterial references are first-class, and the
architecture must not assume a specific clade. Assembly and coordinate handling is explicit and
validated per-organism (and aware that, e.g., bacterial genomes are typically circular, often
single-replicon, gene-dense, intron-poor, and operon-organized — assumptions baked into many
human-centric tools that we must not inherit silently).

This breadth is not academic. A motivating example is ***Gluconobacter oxydans***, an obligately
aerobic acetic-acid bacterium of growing interest in **climate biotech**: it performs rapid,
incomplete periplasmic oxidations, is a workhorse for bio-based production of organic acids and
fine chemicals, and is a candidate chassis for sustainable biomanufacturing and carbon-conscious
processes. Supporting an organism like *G. oxydans* end to end — annotating its genome, designing
CRISPR edits against its particular Cas-compatibility and codon landscape, predicting regulatory and
binding effects on its operons, modeling enzyme structures relevant to its oxidative metabolism, and
proposing engineering experiments — is exactly the kind of cross-organism, multi-capability task the
copilot exists to make tractable. The same machinery must serve a human geneticist, a mouse
neuroscientist, and a microbial metabolic engineer without special-casing any of them.

### Out of scope (non-goals)

- **Clinical diagnosis or treatment decisions.** Outputs are research-grade, not medical advice.
- **Wet-lab automation / direct hardware control.** We design and recommend; we do not execute. We leave lab integration open as a possible future direction.
- **Generating sequences whose primary purpose is hazardous.** See the safety model; flagged
  requests are refused or escalated.
- **Being a model zoo or a raw API gateway.** Value is in orchestration, grounding, and
  presentation — not in exposing every model parameter.
- **A general-purpose chatbot.** Off-domain requests are politely declined or redirected.

## 5. Operating principles

1. **Evidence-grounded by default.** Every non-trivial claim carries provenance: which model/tool,
   which version, which inputs, which references. "I don't know / insufficient evidence" is a valid
   and preferred answer over confident fabrication.
2. **Confidence is explicit.** Predictions report calibrated or qualitative confidence and surface
   the assumptions behind them.
3. **Human-in-the-loop for actionable biology.** Actionable outputs pass through a review gate
   (ADR-0005). The agent never silently advances from "analysis" to "recommended edit".
4. **Reproducible runs.** Every answer is backed by a recorded, re-runnable trace: inputs, tool
   versions, parameters, and outputs are persisted and addressable.
5. **Coordinates are sacred.** Assembly, strand, and 0-/1-based conventions are always explicit and
   validated; silent coordinate errors are treated as critical bugs.
6. **Interpretation over raw dumps.** Default to legible, interactive artifacts and a synthesized
   answer rather than walls of numbers.
7. **Safe by construction.** Safety classification happens early in the graph, not as an
   afterthought.
8. **Organism-agnostic.** No capability hard-codes human-only assumptions.
9. **Private by default / local-first.** The agent's reasoning model runs locally (a local
   open-weight model via Ollama, default Gemma 4 4B) so prompts and sequence data need not leave the
   deployment; remote providers are opt-in and provider-pluggable
   (`specs/services/llm_service.md`).
10. **Transparent by default.** The agent streams its reasoning, plan, and tool activity
    progressively and keeps every result inspectable — depth is opt-in, never hidden
    (`specs/interface/streaming_protocol.md`).

## 6. Target users

Primarily computational and bench biologists, genomics/bioinformatics researchers, and
bio-curious engineers who can pose a precise question but do not want to hand-assemble the toolchain.
Detailed personas live in `specs/product/personas.md`.

## 7. North-star outcome

A researcher can ask a well-posed genomics / molecular-biology question (about DNA, RNA, proteins, or
metabolites) in plain language and, within minutes, receive a trustworthy, cited, visually clear
answer plus a reproducible trace — collapsing what is today hours of multi-tool glue work into a
single conversation.

## 8. North-star metric

**Trustworthy resolution rate**: the fraction of in-domain queries that produce an answer the user
accepts as correct *and* adequately evidenced (cited, confidence-qualified, provenance-complete),
without manual rework. Detailed metrics live in `specs/product/success_metrics.md`.

## 9. What success feels like (illustrative)

- A grad student pastes an rsID and asks "could this be regulatory?" → gets tissue-resolved
  AlphaGenome deltas, the nearest gene/eQTL evidence, a locus plot, and a two-paragraph cited
  interpretation with a confidence note.
- A protein engineer pastes a sequence → gets a predicted structure, a confidence-colored 3D view,
  and a flagged note that a region is low-confidence and worth experimental validation.
- A synthetic biologist asks for a CRISPR knockout strategy → gets candidate guides with on/off
  scores in a sortable table, *held behind a review gate* with the rationale shown before anything is
  framed as a recommendation.

## 10. Related specs

- Technical realization & stack: `documentation/explanation/architecture_overview.md`
- Agent design: `documentation/explanation/multi_agent_architecture.md`,
  `documentation/explanation/harness_and_context_engineering.md`, `specs/agent/`
- Sessions/workspaces: `specs/agent/session_types.md`
- Streaming & UX transparency: `specs/interface/streaming_protocol.md`
- Reasoning model & local-first serving: `specs/services/llm_service.md`;
  improvement loop: `documentation/explanation/post_training.md`
- What we will build, in what order: `specs/product/product_requirements.md`,
  `specs/planning/roadmap.md` (near-term; TBD) and `specs/planning/future-additions.md` (longer-term
  backlog)
- Who we build for: `specs/product/personas.md`, `specs/product/user_stories.md`
- How we know it works: `specs/product/success_metrics.md`, `specs/evaluation/`
- Safety & review posture: `documentation/explanation/safety_model.md`, ADR-0005
