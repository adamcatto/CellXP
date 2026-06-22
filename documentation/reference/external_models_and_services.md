# External Models & Services Catalog

> Status: Draft v0.1 — **catalog / registry**. Authoritative inventory of the external models, tools,
> and data services CellXP can orchestrate. Per-model/per-service detail (exact
> inputs/outputs, params, versions, deployment) is filled in later in `specs/services/` and dedicated
> model files; this doc is the map.
>
> **Curation policy (how this list is kept lean).** One tool per job. When several models do the same
> thing we keep the **open-source**, **latest**, and **most comprehensive / best-performing** option
> and record the rest under *Excluded (superseded)* with the reason. We do **not** list a narrow
> model when a broader model we already keep subsumes it (e.g. we keep AlphaGenome instead of
> Enformer/Borzoi/DeepSEA; we keep Boltz-2 instead of most other folders). Bias: open weights/OSS >
> hosted/restricted, unless the restricted option is materially better with no open equivalent.
>
> **Scope note.** CellXP spans the **central dogma and the molecules genomes act on and
> produce**: DNA, RNA, **proteins**, and **metabolites / small molecules**, plus complexes, pathways,
> and synthetic constructs built from them (see `mission.md` §4). The catalog is organized by
> capability across all of these.
>
> **Legend — Status:** `P0` priority for v1 · `P1` next · `C` candidate/backlog.
> **Legend — Access:** `weights` open weights/self-host · `oss` open-source code · `api` hosted API ·
> `data` database/API (not a model) · `tool` conventional (non-DL) tool.
> **Caveat:** licenses/access change and MUST be verified before integration; the Access column is a
> hint, not a legal statement.

How this maps to the system: each section names the **service** (`src/backend/.../services/<name>/`,
see `architecture_overview.md` §4) that wraps it and the **subgraph** that drives it. The agent
selects among entries per `specs/agent/tool_use_policy.md`; orchestration is in
`architecture_overview.md` §5.1.

> **Out of scope here — the reasoning LLM.** The models below are **domain** oracles. The agent's
> general-purpose **reasoning LLM** (intent/risk/planning/critique/report writing) is a separate
> concern with its own provider abstraction, served **locally via Ollama by default**; see
> `specs/services/llm_service.md`. Don't conflate the two.

---

## 1. Sequence foundation models & variant effect (DNA/RNA)

Service: `services/alphagenome/` (+ a generic sequence-model client) · Subgraph: `variant_effect`,
`annotation`, `binding`.

| Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **AlphaGenome** | Google DeepMind (`alphagenome-pytorch` OSS reimpl) | weights/oss | Multimodal regulatory prediction; variant effect across assays/tissues; expression, chromatin, contacts | P0 |
| **Evo 2** | Arc Institute / NVIDIA | weights | DNA foundation model; generative; zero-shot variant & sequence scoring; cross-species incl. prokaryotes; embeddings | P0 |

*Excluded (superseded):* Enformer & Borzoi (regulatory/expression subsumed by AlphaGenome);
DeepSEA/Beluga & Sei (outdated chromatin-effect models, superseded by AlphaGenome); Nucleotide
Transformer / DNABERT-2 / HyenaDNA / Caduceus / GENA-LM (general genomic LM/embeddings — Evo 2
covers embeddings + zero-shot scoring with longer context and broader species; revisit only if a
lightweight embedding-only model is needed).

## 2. Splicing & RNA regulation

Service: `services/alphagenome/` · Subgraph: `variant_effect`, `annotation`.

| Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **SpliceAI** | Illumina | weights/oss | Splice-altering variant prediction (standard, OSS) | P0 |
| **APARENT2** | Seelig lab | weights/oss | Polyadenylation / 3′UTR / APA effects (distinct task) | C |

*Excluded (superseded):* Pangolin (splicing overlaps SpliceAI; AlphaGenome also predicts splicing —
keep SpliceAI as the dedicated standard, revisit Pangolin only for multi-tissue gaps).

## 3. Protein structure prediction

Service: `services/structure/` · Subgraph: `structure`.

| Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **ESMFold** | Meta | weights | Fast single-sequence protein structure (no MSA) | P0 |
| **Boltz-2** | MIT (Boltz) | weights/oss | AF3-class: complexes/multimers, protein–ligand, **NA-aware** structure **+ binding affinity** | P0 |
| **ESM-2** | Meta | weights | Protein embeddings for downstream tasks (not structure) | P1 |

*Excluded (superseded):* AlphaFold2/ColabFold, Chai-1, RoseTTAFold2 / RF-All-Atom, OpenFold,
OmegaFold — all general structure predictors subsumed by the ESMFold (fast/no-MSA) + Boltz-2
(comprehensive/complexes/NA/ligand, fully OSS) pairing.

## 4. Nucleic-acid structure (RNA/DNA)

Service: `services/structure/` · Subgraph: `structure`.

| Model/Tool | Source | Access | Task | Status |
|---|---|---|---|---|
| **ViennaRNA (RNAfold)** | TBI Vienna | tool/oss | RNA secondary structure / MFE (workhorse) | P0 |
| **EternaFold** | Stanford | oss | Learned RNA secondary structure (higher accuracy) | C |
| **RhoFold** | various | weights/oss | RNA 3D structure (single-chain) | C |

*Note:* protein–NA and NA-containing **complex** 3D structure is handled by **Boltz-2** (§3).
*Excluded (superseded):* RoseTTAFoldNA (use Boltz-2); SPOT-RNA/UFold/MXfold2 (secondary structure —
ViennaRNA/EternaFold cover); DRfold (RhoFold covers RNA 3D).

## 5. DNA / chromatin structure & shape

Service: `services/structure/` · Subgraph: `structure`.

| Model/Tool | Source | Access | Task | Status |
|---|---|---|---|---|
| **DNAshapeR** | USC | tool/oss | Sequence → DNA shape features (MGW, roll, twist, …) | P0 |
| **Orca** | Princeton | weights/oss | Multiscale 3D-genome / Hi-C contact prediction (kb→Mb) | P1 |
| **NuPoP** | — | tool/oss | Nucleosome occupancy/positioning (distinct task) | C |

*Excluded (superseded):* Akita (single-scale contact prediction — Orca subsumes; AlphaGenome also
emits contacts).

## 6. TF binding, footprinting & motifs

Service: `services/binding/` · Subgraph: `binding`.

| Model/Tool | Source | Access | Task | Status |
|---|---|---|---|---|
| **AlphaGenome (binding heads)** | DeepMind | weights | TF binding / accessibility prediction & variant deltas | P0 |
| **ChromBPNet** | Kundaje lab | weights/oss | Base-resolution accessibility / TF footprint; variant effect | P1 |
| **MEME Suite (FIMO/MEME/TOMTOM)** | — | tool/oss | Motif scan / discovery / comparison | P0 |
| **JASPAR** | DB | data | Open TF motif PWM/PFM database | P0 |
| **TF-MoDISco** | Kundaje lab | oss | Motif discovery from model attributions (distinct) | C |

*Excluded (superseded):* BPNet (ChromBPNet supersedes); HOCOMOCO (JASPAR kept as primary open motif
DB).

## 7. Genome annotation & gene finding (eukaryotic + prokaryotic)

Service: `services/reference/`, `services/annotation` · Subgraph: `annotation`.
*(Prokaryotic tools are first-class — see the G. oxydans motivation in `mission.md`.)*

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **Pyrodigal (Prodigal)** | — | tool/oss | Bacterial/archaeal gene calling | P0 |
| **Bakta** | — | tool/oss | Full bacterial genome annotation (uses Prodigal) | P0 |
| **Helixer** | — | weights/oss | DL eukaryotic gene-structure annotation | P1 |
| **DeepRegFinder** | — | weights/oss | Regulatory-element annotation | P1 |
| **tRNAscan-SE / Barrnap** | — | tool/oss | tRNA / rRNA detection | P1 |
| **Infernal + Rfam** | — | tool/data | ncRNA detection (covariance models) | P1 |
| **InterProScan / eggNOG-mapper** | EBI / — | tool/data | Functional / domain / ortholog annotation | P1 |
| **antiSMASH** | — | tool/oss | Biosynthetic gene clusters / secondary metabolites (biotech-relevant) | P1 |

*Excluded (superseded):* Prokka (Bakta supersedes for bacterial annotation); AUGUSTUS (Helixer
supersedes for eukaryotic gene structure).

## 8. Variant annotation & interpretation

Service: `services/reference/`, `services/gwas/` · Subgraph: `variant_effect`, `gwas`.

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **Ensembl VEP** | EBI | tool/oss | Variant consequence annotation (comprehensive, OSS) | P0 |
| **AlphaMissense** | DeepMind | data/weights | Missense pathogenicity | P1 |

*Excluded (superseded):* SnpEff/ANNOVAR (VEP kept as primary); ESM1v / EVE (missense effect covered
by AlphaMissense + ESM-2 zero-shot); CADD (outdated composite score).

## 9. GWAS / QTL / statistical genetics

Service: `services/gwas/` · Subgraph: `gwas`. *(Mostly data + statistical tools, not DL models —
little redundancy to prune.)*

| Tool/Data | Source | Access | Task | Status |
|---|---|---|---|---|
| **GWAS Catalog** | EBI/NHGRI | data | Trait–variant associations | P0 |
| **Open Targets (Genetics/Platform)** | OT | data/api | Target–disease + L2G evidence | P0 |
| **eQTL Catalogue / GTEx** | EBI / GTEx | data | eQTL/sQTL associations | P0 |
| **gnomAD / dbSNP / ClinVar** | Broad / NCBI | data | Allele frequency, IDs, clinical significance | P0 |
| **SuSiE** | — | tool/oss | Fine-mapping (credible sets) | P1 |
| **coloc** | — | tool/oss | Colocalization | P1 |
| **PLINK / LDSC** | — | tool/oss | LD, heritability, genetic correlation | P1 |

*Excluded (superseded):* FINEMAP (SuSiE kept as primary fine-mapper).

## 10. CRISPR & genome editing design

Service: `services/crispr/` · Subgraph: `crispr`. **Actionable → review-gated (FR-25/26).**

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **Rule Set 2 / Azimuth (Doench)** | Broad | weights/oss | Cas9 on-target efficiency (standard) | P0 |
| **CFD score** | — | tool/oss | Off-target specificity scoring | P0 |
| **Cas-OFFinder** | — | tool/oss | Genome-wide off-target enumeration | P0 |
| **CRISPOR** | — | tool/oss | End-to-end guide design + aggregated scoring | P1 |
| **BE-Hive** | — | weights/oss | Base-editing outcome prediction | P1 |
| **PRIDICT** | — | weights/oss | Prime-editing efficiency/outcome | P1 |

The packaged X5 worker pins Cas-OFFinder 2.4.1, Azimuth v2.0, and a CRISPOR CFD source snapshot in
`services/crispr/worker_manifest.json`. These identities describe packaged sources, not live
acceptance; deployments additionally attest their reference/index manifest.

*Excluded (superseded):* DeepHF/DeepSpCas9 (on-target — Rule Set 2 kept as standard; revisit for
best-in-class accuracy); CHOPCHOP (CRISPOR kept as primary suite); DeepPrime (PRIDICT kept for prime
editing). Cas-variant/PAM trade-offs live in `specs/biology/crispr_design.md`.

## 11. Model-guided edit design (inverse design) — *flagship composed capability*

Service: orchestrated across `services/alphagenome/` + `services/crispr/` (+ future `editdesign`) ·
Subgraph: future `edit_design` (composes `variant_effect` ⇄ `crispr`). **Actionable → review-gated
(FR-25/26).**

This is **not a single model** but an **orchestration pattern** that inverts the forward
effect-prediction models. The forward question is "what does this edit do?"; the inverse question is
**"given a desired functional effect, which edit(s) achieve it with minimal off-target and collateral
effects?"** The agent runs a closed optimization loop over the edit space using the catalog's
existing models as components:

```
target effect ─▶ propose candidate edits ─▶ forward-predict effect (AlphaGenome/Evo2)
      ▲                                                   │
      └──────────── score & select ◀── off-target + feasibility + collateral checks
        (multi-objective: maximize on-target effect, minimize off-target / disruption)
```

| Component role | Models/tools used | From section |
|---|---|---|
| Forward effect oracle (objective) | **AlphaGenome**, **Evo 2** (+ SpliceAI, ChromBPNet for specific effects) | §1, §2, §6 |
| Edit proposal / realizability | **CRISPR** designers, base/prime-edit outcome models (Rule Set 2, BE-Hive, PRIDICT) | §10 |
| Off-target / specificity penalty | **Cas-OFFinder**, **CFD** (genome-wide) | §10 |
| Collateral-effect penalty | forward models on *other* loci/regulatory elements (don't break what works) | §1, §6 |
| Optimizer / search | exhaustive (small edit sets), greedy/beam, evolutionary/MCMC, **gradient-guided** (differentiable `alphagenome-pytorch`), or Evo 2 guided generation | — |

**Problem framing.** Inputs: a *desired effect* expressed as a target on a forward-model readout —
e.g. "increase expression of gene X in tissue Y", "create/abolish a TF binding site", "shift
splicing toward isoform Z", "tune a regulatory element's activity by N%", "knock down without
disrupting neighbors". Output: a ranked set of **candidate edit strategies**, each with predicted
on-target effect (+ confidence), a genome-wide off-target profile, editing feasibility (system,
PAM/window, efficiency), and collateral-effect assessment — exported as edit/design files and
**held behind the human-review gate** before any framing as a recommendation.

**Why it's a flagship.** It directly serves the bioengineer / genome-editing-engineer persona (P6)
and embodies the agentic thesis: composing forward predictors + editing tools + an optimizer into a
goal-directed loop, with safety and off-target minimization as first-class objectives, not
afterthoughts. Detailed objective/constraint formulation and search strategy live in
`specs/biology/inverse_edit_design.md` (to be written) and `specs/services/` (orchestration in
`architecture_overview.md` §5.1).

## 12. Protein & sequence design (engineering)

Service: `services/structure/` (+ future `design`) · Subgraph: future `design`.
**Generative → review-gated when actionable.**

| Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **LigandMPNN (ProteinMPNN)** | Baker lab | weights/oss | Fixed-backbone sequence design (ligand/NA-aware superset of ProteinMPNN) | P1 |
| **RFdiffusion (All-Atom)** | Baker lab | weights/oss | Backbone / binder / motif-scaffold generation | P1 |
| **ESM3 (open)** | EvolutionaryScale | weights | Generative protein (sequence/structure/function) | C |

*Excluded (superseded):* ProteinMPNN (LigandMPNN is a strict superset); ProGen2 / ProtGPT2
(generative sequence — ESM3 kept as broader open generative model).

## 13. Small molecules, metabolites, docking & cheminformatics

Service: future `binding` / `chem` · Subgraph: `binding` / future. *(Supports protein–ligand,
metabolite, and metabolic-engineering tasks; ChEMBL MCP available.)*

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **RDKit** | OSS | tool/oss | Cheminformatics: parsing, descriptors, conformers, similarity | P1 |
| **Boltz-2 (affinity)** | MIT | weights/oss | Co-folding + binding-affinity prediction | P1 |
| **ChEMBL** | EBI | data/api | Bioactivity database (MCP available) | P1 |
| **ChEBI / HMDB** | EBI / — | data | Metabolite identities, ontologies, properties | P1 |
| **DiffDock** | MIT | weights/oss | Diffusion-based molecular docking | C |

*Excluded (superseded):* Gnina/smina/AutoDock Vina (physics docking — DiffDock kept as the DL
option; revisit physics docking if needed); AiZynthFinder/retrosynthesis (out of v1 scope).

## 14. Networks & systems biology (GRN & metabolic models)

Service: future `systems` (composes `annotation` + `binding` + `variant_effect`) · Subgraph: future
`systems`. *(Powers the composed/systems-level patterns in `task_patterns.md` §2–§6: variant→GRN,
variant→metabolism, network inference, strain engineering.)*

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **COBRApy** | OSS | tool/oss | Genome-scale metabolic model analysis — FBA/FVA, knockouts, strain design | P1 |
| **CarveMe** | OSS | tool/oss | Automated GEM reconstruction from genome/annotation | C |
| **ModelSEED / BiGG** | — | tool/data | GEM reconstruction templates + curated model database | C |
| **GRNBoost2 / GENIE3 (arboreto)** | OSS | tool/oss | Expression-based GRN edge inference | C |
| **SCENIC / pySCENIC** | OSS | tool/oss | Motif-pruned regulon / GRN inference (incl. single-cell) | C |
| **ABC model (activity-by-contact)** | Engreitz lab | oss | Enhancer→gene linking (regulatory edges) | C |

*Notes:* GEM analysis (COBRApy) is `P1` because it underpins the bacterial metabolic patterns;
reconstruction + GRN inference are `C` until those subgraphs are built. Forward effect oracles
(AlphaGenome §1 / Evo 2 §1 / ChromBPNet §6) provide sequence-grounded edge/effect estimates that
feed these network methods.

## 15. Protein & enzyme function (annotation)

Service: `services/reference/`/`services/annotation` (+ future `function`) · Subgraph: `annotation`.
*(Enables enzyme/EC assignment for metabolic-engineering use-cases like G. oxydans.)*

| Tool/Model | Source | Access | Task | Status |
|---|---|---|---|---|
| **InterProScan / eggNOG-mapper** | EBI / — | tool/data | Domains, families, GO, orthology (see §7) | P1 |
| **CLEAN** | — | weights/oss | Enzyme EC-number prediction from sequence | C |
| **DeepFRI** | — | weights/oss | Structure/sequence → GO function prediction | C |

## 16. DNA origami / nanotech

Service: `services/origami/` · Subgraph: `origami`. **Actionable → review-gated.**

| Tool | Source | Access | Task | Status |
|---|---|---|---|---|
| **cadnano / scadnano** | — | tool/oss | Origami design + canonical export format | P0 |
| **oxDNA / oxRNA** | — | tool/oss | Coarse-grained MD simulation of nanostructures | P1 |
| **DAEDALUS / PERDIX / TALOS / ATHENA** | MIT | tool/oss | Automated wireframe/scaffold routing | P1 |
| **CanDo** | — | tool/api | Finite-element mechanical prediction | C |

*Excluded (superseded):* MrDNA (oxDNA kept as primary nanostructure simulator).

## 17. Literature & knowledge retrieval (RAG / data)

Service: `services/rag/` · Subgraph: `rag`. *(Several available as MCP servers — see `mcps/`.)*

| Source | Access | Task | Status |
|---|---|---|---|
| **PubMed / PMC** | data/api | Primary literature retrieval | P0 |
| **Ensembl / UCSC / NCBI** | data/api | Reference genomes, gene models, assemblies | P0 |
| **UniProt** | data/api | Protein sequences/function | P0 |
| **bioRxiv / medRxiv** | data/api | Preprints | P1 |
| **Reactome / KEGG / GO** | data/api | Pathways, ontologies | P1 |

## 18. Single-cell / transcriptomics (RNA — exploratory scope)

Service: future `transcriptomics` · Subgraph: future. *(RNA is in domain; gated as exploratory.)*

| Model/Tool | Source | Access | Task | Status |
|---|---|---|---|---|
| **scVI / scANVI (scvi-tools)** | scverse | weights/oss | Integration, batch correction, label transfer | C |
| **scGPT** | — | weights | Single-cell foundation model | C |

*Excluded (superseded):* Geneformer (scGPT kept as the single-cell foundation model option).

---

## 19. Integration contract (applies to every entry)

Regardless of category, anything orchestrated MUST be wrapped to satisfy the system contract:

1. **Uniform service interface** — exposed via `services/base.py` + `services/registry.py`; the agent
   never calls a model directly.
2. **Normalized I/O** — accepts normalized domain inputs (organism/assembly/strand/alphabet explicit;
   bacterial-circular-aware) and returns structured results + artifact(s).
3. **Provenance + confidence** — records model identity, version/weights, params, and inputs to the
   run trace; attaches confidence (`FR-23`, `FR-24`, `evidence_and_confidence.md`).
4. **Selection metadata** — declares task(s), modality, organism applicability, latency/cost tier,
   and fidelity so the planner can choose among overlapping options
   (`specs/agent/tool_use_policy.md`).
5. **Async where heavy** — GPU/long models run as jobs (`architecture_overview.md` §7).
6. **Safety posture** — actionable/generative capabilities route through the human-review gate
   (`FR-25/26`, ADR-0005).
7. **Pluggability** — adding/swapping an entry is a service-level change behind the same contract
   (`NFR-11`, ADR-0003); endpoints configured via env (`*_SERVICE_URL`).

## 20. Maintenance

- This catalog is the index; **per-entry detail** goes in `specs/services/<service>.md` and dedicated
  model files (created later).
- Apply the **curation policy** (top of file) on every change: one tool per job; keep the
  open/latest/most-comprehensive option; move the rest to *Excluded (superseded)* with a reason.
- When an entry is integrated, update its Status and link its spec file.
- Cross-references: capabilities ↔ `specs/product/product_requirements.md`; scope ↔ `mission.md` §4;
  orchestration ↔ `architecture_overview.md` §5.1; methodology ↔ `specs/biology/`.
