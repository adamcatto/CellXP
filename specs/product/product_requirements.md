# Product Requirements

> Status: Draft v0.1. Derives from `specs/product/mission.md` and
> `documentation/explanation/architecture_overview.md`. Requirements use RFC-2119 keywords
> (MUST / SHOULD / MAY). Each requirement is IDed (`FR-*` functional, `NFR-*` non-functional,
> `CR-*` constraint) so downstream specs, tests, and evals can reference it.

## 1. Purpose & audience

This document defines *what* CellXP must do and the quality bars it must meet, at a level
detailed enough to drive service, agent, and interface specs. It does not prescribe UI layout (see
`specs/interface/`) or biological method details (see `specs/biology/`).

## 2. Product summary

A chat-driven genomics & molecular-biology copilot: within a persistent workspace, the user poses a
question about DNA, RNA, proteins, or metabolites — in natural language and/or as sequence data; an
orchestrating multi-agent system plans and runs the work across specialized services and returns a
cited, confidence-qualified answer plus interactive, reproducible artifacts, streaming its reasoning
and tool activity as it goes.

## 3. Scope of this release line (v1)

**In:** the capability domains in the mission (variant effect, GWAS/QTL, CRISPR design, annotation,
binding, structure, **protein function/design, metabolites/cheminformatics**, inverse edit design,
networks/systems-level analysis, origami, RAG, visualization) across DNA, RNA, proteins, and
metabolites/small molecules; organism-agnostic; chat + workspace UI with **persistent typed
sessions**; **progressive streaming** of reasoning/tool activity; a **local-first, pluggable**
reasoning LLM; run provenance; human-review gate; evaluation harness.

**Out (v1):** multi-user real-time collaboration, **in-product training/fine-tuning of models**,
mobile-native apps, clinical/regulated use, wet-lab execution. (Tracked in
`specs/planning/future-additions.md`.)

> Note: *offline* post-training of the agent's **reasoning LLM** (SFT/DPO/RLVR) is a separate roadmap
> track (`specs/training/post_training.md`), distinct from "in-product training"; the **domain
> foundation models** are used at released weights and are never fine-tuned in-product.

## 4. Personas (summary)

Full detail in `specs/product/personas.md`. Primary: **computational biologist**, **bench/bench-adjacent
biologist**, **bio-curious engineer**, **bioengineer / genome-editing & tissue engineer**
(designer-builder). Secondary: **PI/reviewer** (audits runs), **platform
operator** (runs the system).

## 5. Functional requirements

### 5.1 Conversation & orchestration

- **FR-1** The system MUST accept a free-text query and return a synthesized natural-language answer.
- **FR-2** The system MUST classify query **intent** and route to the appropriate capability/subgraph.
- **FR-3** The system MUST classify query **risk/safety** early and gate or refuse accordingly
  (see §5.8).
- **FR-4** The system MUST resolve biological **entities** from the query (genes, variants,
  intervals, sequences, organisms, assemblies) and confirm ambiguous resolutions with the user.
- **FR-5** The system MUST plan multi-step tasks and execute them across one or more services in a
  single run.
- **FR-6** The system MUST stream progress to the UI **progressively** as the run proceeds — at
  minimum: intent, reasoning/"thinking" (under a collapsible, user-toggleable disclosure), tool-call
  activity with input/output summaries, partial results, and artifacts (placeholder → populated). It
  MUST NOT block until full completion to show activity, and depth MUST be opt-in (clean answer by
  default, inspectable on demand). Contract: `specs/interface/streaming_protocol.md`.
- **FR-7** The system SHOULD ask clarifying questions when the query is under-specified rather than
  guessing on consequential parameters (organism, assembly, edit intent). When it does, it SHOULD
  present **selectable options** (with a recommended default) and allow a free-text addition
  ("yes, and …" / "Other"), so the user can answer in a single step
  (`specs/interface/streaming_protocol.md` §7).
- **FR-8** The system MUST decline or redirect clearly **out-of-domain** requests — i.e. requests not
  about molecular biology (DNA, RNA, proteins, metabolites, or the complexes/networks/constructs built
  from them).

### 5.2 Input handling

- **FR-9** The system MUST accept these input forms: gene symbols/IDs, rsIDs, HGVS, genomic
  intervals, raw DNA/RNA/protein sequences (incl. FASTA), and organism/assembly selectors.
- **FR-10** The system MUST validate and normalize inputs (e.g. coordinate base, strand, assembly,
  alphabet) and surface validation errors with actionable messages.
- **FR-11** The system MUST require or infer-then-confirm the organism and assembly before any
  coordinate-dependent operation.
- **FR-12** The system SHOULD support file upload for sequences/variant lists within published size
  limits (limit defined in `specs/interface/` / config).

### 5.3 Capability requirements

Each capability MUST: accept normalized inputs, return a structured result + one or more artifacts,
attach provenance + confidence, and be invokable both directly (API) and via the agent.

- **FR-13 Variant effect** — predict regulatory/functional effects of coding & non-coding variants
  with tissue/assay resolution (AlphaGenome/Evo2-class). Output: per-assay deltas + track artifact.
- **FR-14 GWAS/QTL** — look up trait associations, LD, fine-mapping, and colocalization for a
  variant/locus/gene. Output: association evidence + locus plot artifact.
- **FR-15 CRISPR design** — design gRNAs with on/off-target scores; support base & prime editing.
  Output: ranked guide table artifact. **Actionable → review-gated (FR-25).**
- **FR-16 Annotation** — annotate sequences/intervals with gene models, regulatory features, motifs,
  ORFs. Output: annotation track artifact.
- **FR-17 Binding** — scan TF motifs, footprints, and predict occupancy/binding deltas. Output:
  motif/track artifacts.
- **FR-18 Structure** — predict protein/nucleic-acid/complex structure, DNA shape, nucleosome
  positioning, and chromatin contacts. Output: 3D structure and/or contact-map artifacts with
  per-residue confidence.
- **FR-18a Protein function & design** — annotate protein/enzyme function (EC, domains, GO,
  orthology), and design protein sequences/binders given a backbone or target (e.g. LigandMPNN,
  RFdiffusion). Output: function annotations and/or candidate designs. **Generative/design output →
  review-gated (FR-25).**
- **FR-18b Metabolites & small molecules** — cheminformatics (parsing, descriptors, similarity),
  protein–ligand binding/affinity prediction, and genome-scale metabolic modeling (pathways, flux)
  for metabolic-engineering use-cases. Output: molecular/affinity/pathway artifacts.
- **FR-18c Model-guided edit design (inverse design)** — given a *desired functional effect*
  (expressed as a target on a forward-model readout — e.g. raise expression of gene X in tissue Y,
  create/abolish a binding site, shift splicing, tune a regulatory element), the system MUST search
  the realizable edit space to propose edit strategies that achieve it, optimizing a multi-objective
  that **maximizes the on-target effect while minimizing off-target and collateral effects**. It MUST
  compose forward effect models (FR-13/17) as the objective oracle, CRISPR/base/prime-edit designers
  (FR-15) for realizability, and genome-wide off-target analysis as a penalty. Output: ranked
  candidate edits with predicted effect + confidence, off-target profile, editing feasibility, and
  collateral-effect assessment. **Actionable → review-gated (FR-25).**
- **FR-18d Networks & systems-level analysis** — infer and analyze biological networks and propagate
  perturbations across scales: (a) **gene regulatory network (GRN)** inference and variant-impact
  propagation (how a regulatory variant rewires TF→target edges and dysregulates downstream
  genes/pathways); (b) **metabolic network** reconstruction (genome → genome-scale metabolic model)
  and analysis (FBA/FVA); and (c) **variant→metabolism** prediction (how coding/regulatory variants
  shift flux, growth, or metabolite yield, esp. in bacterial strains). The system MUST realize these
  by composing forward models (FR-13/17/18a/b) with network/GEM tools, and MUST record provenance and
  compounded uncertainty across the chain (FR-23/24). Output: network/flux/pathway artifacts +
  interpretation. Orchestration recipes: `documentation/explanation/task_patterns.md`.
- **FR-19 DNA origami** — design scaffold routing + staples under constraints; export
  cadnano-compatible output. Output: origami layout artifact. **Actionable → review-gated (FR-25).**
- **FR-20 Literature grounding (RAG)** — retrieve and cite primary literature/databases supporting
  the answer. Output: citation set linked into the report.
- **FR-21 Visualization** — render any capability result as an interactive, exportable artifact.

### 5.4 Evidence, provenance & confidence

- **FR-22** Every substantive claim in an answer MUST link to evidence (model output, DB record,
  or citation).
- **FR-23** Every prediction MUST carry a confidence indicator (calibrated value or qualitative
  band) and note key assumptions/limitations.
- **FR-24** Every run MUST record a complete, addressable trace: inputs, normalized inputs, each tool
  call with versions/parameters, outputs, and artifacts — sufficient to reproduce the result.

### 5.5 Human review (actionable biology)

- **FR-25** Outputs classified as **actionable** (CRISPR edits, primers, origami designs, anything
  proposing a physical intervention) MUST pass through a human-review gate before being presented as
  a recommendation; pre-gate they are shown as candidates with rationale (ADR-0005).
- **FR-26** The review gate MUST present the proposed action, supporting evidence, and risks, and
  MUST require explicit user acknowledgement to proceed.

### 5.6 Artifacts & workspace

- **FR-27** The system MUST render results as typed, interactive **artifacts** in the workspace
  (genome tracks, locus plots, 3D structures, contact maps, guide tables, origami layouts,
  annotation tracks, reports).
- **FR-28** Artifacts MUST be addressable (deep-linkable), persisted, and exportable (at minimum:
  image/PNG/SVG where visual, and the underlying structured data).
- **FR-29** Artifacts MUST link back to the run/message and evidence that produced them.

### 5.7 Runs, history & reproducibility

- **FR-30** The system MUST persist runs and expose a run inspector (timeline of nodes/tool calls,
  inputs/outputs).
- **FR-31** Users MUST be able to revisit prior runs and their artifacts.
- **FR-32** The system SHOULD support re-running a prior run with identical inputs to verify
  reproducibility.

### 5.8 Safety

- **FR-33** The system MUST refuse or escalate requests whose primary purpose is hazardous (per
  `documentation/explanation/safety_model.md`).
- **FR-34** Safety classification MUST occur before capability execution, not after.
- **FR-35** Refusals MUST be explained and, where possible, offer a safe alternative.

### 5.9 Sessions & workspaces

- **FR-36** The system MUST support persistent **sessions (workspaces)** that group multiple runs and
  carry context across them — resolved entities, accumulated artifacts, workspace files, and defaults
  (`specs/agent/session_types.md`).
- **FR-37** A session MAY have a **type** (e.g. variant interpretation, genome editing, strain
  optimization, structure & binding, annotation & discovery, DNA nanotech, literature) that sets
  sensible defaults — organism/assembly, suggested macros, enabled capabilities, persona, and review
  posture. Session typing MAY be explicit or inferred-then-confirmed.
- **FR-38** A session MUST inject its defaults into new runs **without** preventing per-run override,
  and MUST NOT weaken safety: a session cannot disable the safety gate or auto-approve actionable
  biology (CR-4 still holds; ADR-0005).
- **FR-39** Actionable-heavy session types (genome editing, strain optimization, DNA nanotech) MUST
  default to a **stricter review posture** that applies the human-review gate broadly (FR-25/26).

## 6. Non-functional requirements

- **NFR-1 Responsiveness** — first streamed token/plan SHOULD appear within ~3 s of submission for
  typical queries; the UI MUST show liveness for long-running (GPU) tasks.
- **NFR-2 Throughput/async** — heavy/GPU work MUST run as async jobs without blocking the API or
  other users.
- **NFR-3 Correctness invariants** — coordinate/assembly/strand handling MUST be explicit and
  validated; a silent coordinate error is a release-blocking (P0) defect.
- **NFR-4 Reproducibility** — given a persisted run, re-execution with the same inputs/tool versions
  MUST produce equivalent results (within documented model nondeterminism).
- **NFR-5 Observability** — runs, tool calls, latencies, and errors MUST be logged and inspectable.
- **NFR-6 Reliability** — a single service/tool failure MUST degrade gracefully (partial results +
  clear error), not crash the whole run.
- **NFR-7 Security/privacy** — secrets via env only; user-uploaded sequences treated as private;
  no secret leaks in logs/traces. Inference is **local-first by default**: the reasoning LLM runs
  on-host (Ollama; `specs/services/llm_service.md`) so prompts/sequence data need not leave the
  deployment; any remote-provider use is opt-in and audit-logged.
- **NFR-8 Portability** — runs locally (compose) and on Kubernetes from the same images.
- **NFR-9 Accessibility** — UI SHOULD meet WCAG 2.1 AA for core flows; visualizations SHOULD provide
  non-color-only encodings and data export.
- **NFR-10 Testability/evals** — capabilities MUST be covered by golden-query evals + rubrics; CI
  gates on them.
- **NFR-11 Extensibility** — adding a new capability MUST follow the service+subgraph pattern without
  changing the agent's core contract.

## 7. Constraints

- **CR-1** Stack is fixed by `architecture_overview.md` (Python/FastAPI/LangGraph backend, Next.js
  frontend, Postgres/Redis/object-store/vector index).
- **CR-2** Specs are contracts (ADR-0004); implementation MUST conform or the spec is revised first.
- **CR-3** Service boundaries are logical first, microservices only when justified (ADR-0003).
- **CR-4** Organism-agnostic: no capability may hard-code human-only assumptions.
- **CR-5** Not for clinical/diagnostic use; this limitation MUST be surfaced to users.
- **CR-6** The agent's reasoning LLM MUST be **local-first by default and provider-pluggable** — no
  business logic hard-codes a vendor/endpoint; the default is a local open-weight model (Gemma 4 4B)
  via Ollama (`specs/services/llm_service.md`). Distinct from the domain foundation models, which are
  used at released weights (CR-1).

## 8. Acceptance (release gate for v1)

A release candidate is acceptable when: all `FR-*` marked MUST are implemented and covered by tests;
`NFR-3` (coordinates) and all safety `FR-33..35` pass with zero known P0s; the golden-query eval
suite meets the thresholds in `specs/product/success_metrics.md` and `specs/evaluation/`; and every
shipped capability produces a provenance-complete, confidence-qualified artifact.

## 9. Traceability

Requirements map forward to: services (`specs/services/`), agent (`specs/agent/`), interface
(`specs/interface/`), data (`specs/data/`), and evals (`specs/evaluation/`). User-facing scenarios
that exercise these requirements live in `specs/product/user_stories.md`; measurement in
`specs/product/success_metrics.md`.
