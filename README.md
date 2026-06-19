# CellXP

CellXP is a full-stack, LangGraph-orchestrated agentic copilot for genomics and molecular biology. It turns a question about DNA, RNA, proteins, or metabolites — posed in natural language and/or as sequence data — into a grounded, reproducible, and visually legible answer, for any organism from humans to mice to bacteria.

> **Project status: spec-first, pre-implementation.** The `specs/` and `documentation/` trees are the source of truth. Most of `src/` is scaffold/stubs — real directory layout, mostly empty implementations. See `.agents/onboarding.md` for how to navigate the repo.

---

## What it does

Modern genomics is bottlenecked by orchestration. Answering even a routine question — "is this non-coding variant likely regulatory, and in which tissue?", "design three CRISPR guides for this locus", "predict the structure of this RNA and show me the contact map" — requires locating the right reference assembly, normalizing messy inputs, picking and correctly invoking the right model, stitching outputs together, and producing a figure with a defensible conclusion. Each step is tractable; together they are exhausting and rarely reproducible.

CellXP collapses that into a single conversation. Input is multimodal: natural language, raw sequences (FASTA, DNA/RNA/protein, rsIDs, HGVS, genomic intervals, gene symbols), uploaded files, or any combination. The agent classifies intent, normalizes inputs, resolves biological entities, plans a sequence of subtasks, dispatches them to specialized services, integrates the evidence, and returns:

1. A written answer with inline citations and explicit confidence
2. One or more interactive **artifacts** (genome-browser tracks, locus plots, 3D structures, contact maps, guide tables, origami layouts)
3. A fully inspectable **run trace** of every tool call, input, and output

This is an agentic system, not a one-shot question-answerer. It reasons over multiple steps, decomposes and revises its own plan, chains artifacts (e.g. annotate → predict effect → design a guide → visualize), persists outputs to the workspace, and proposes follow-up analyses. Anything that proposes actionable biology (a CRISPR edit, a primer, an origami design) passes through a **human-review gate** before being presented as a recommendation.

---

## Capabilities

| Capability | What it does | Key models/tools |
|---|---|---|
| **Variant effect prediction** | Tissue/assay-resolved regulatory and functional effect prediction for coding and non-coding variants | AlphaGenome, Evo 2 |
| **GWAS / QTL lookup** | Trait-association lookup, fine-mapping, LD, colocalization, Open Targets-style evidence aggregation | GWAS Catalog, Open Targets |
| **CRISPR design** | gRNA design, on-/off-target scoring, base editing, prime editing, Cas selection | Rule Set 3, Azimuth, CRISPRscan |
| **Inverse edit design** | Given a desired functional effect, search the edit space to find genome edits that achieve it while minimizing off-target effects — composed from forward models + CRISPR design | AlphaGenome/Evo 2 as objective |
| **Sequence annotation** | Gene models, regulatory features, motifs, ORFs, functional elements (eukaryote + prokaryote) | AlphaGenome, DeepRegFinder |
| **Binding-site prediction** | TF motif scanning, footprinting, occupancy deltas | AlphaGenome, FIMO/JASPAR |
| **Structure prediction** | Protein structure, nucleic-acid structure, DNA shape, nucleosome positioning, chromatin contact maps | ESMFold, Boltz-2 |
| **Protein function & design** | Enzyme annotation (EC, GO, domains), binder/sequence design | LigandMPNN, RFdiffusion |
| **Metabolites & small molecules** | Protein–ligand binding/affinity, genome-scale metabolic modeling, flux analysis | — |
| **Networks & systems analysis** | GRN inference, metabolic network reconstruction, variant→flux→phenotype reasoning | — |
| **DNA origami / nanotech** | Scaffold routing, staple design, constraint checking, cadnano export | oxDNA, cadnano |
| **Literature grounding (RAG)** | Retrieval and citation of primary literature and databases | PubMed, vector index |
| **Visualization** | Interactive, exportable scientific figures for all of the above | Plotly, Mol*, IGV.js |

**Organisms:** organism-agnostic by design. Human (GRCh38), mouse, and bacterial references are first-class. The architecture handles circular bacterial genomes, operon structure, and organism-specific coordinate conventions. A motivating example is *Gluconobacter oxydans* — a climate-biotech chassis for bio-based production — which the copilot supports end-to-end without special-casing.

---

## Architecture

### Agent graph

The agent is a **hierarchical LangGraph supervisor**. The top-level graph routes through a fixed spine of core nodes; capability work fans out to independent subgraphs.

```
START
  └─ input_normalizer       # parse/normalize inputs (sequences, rsIDs, HGVS, intervals, files)
       └─ intent_classifier  # classify what the user is asking
            └─ entity_resolver  # resolve biological entities (genes, variants, organisms)
                 └─ risk_classifier  # early safety gate (FR-33/34)
                      └─ planner      # decompose into subtasks; build the plan
                           └─ task_selector  ──── conditional routing ────►
                                                    ├─ variant_effect_subgraph
                                                    ├─ gwas_subgraph
                                                    ├─ crispr_subgraph
                                                    ├─ annotation_subgraph
                                                    ├─ binding_subgraph
                                                    ├─ structure_subgraph
                                                    ├─ origami_subgraph
                                                    ├─ rag_subgraph
                                                    └─ visualization_subgraph
                                                              │
                                                    evidence_integrator
                                                              │
                                                           critic
                                                              │
                                                    [human_review_gate]  ← for actionable outputs
                                                              │
                                                    report_generator
                                                              │
                                                            END
```

Each capability subgraph owns its own service client, evidence collection, and artifact production. A `human_review_gate` node intercepts any actionable output (CRISPR designs, inverse edits, origami) before it is presented as a recommendation.

### Tech stack

| Layer | Technology |
|---|---|
| **Agent orchestration** | LangGraph (`langgraph>=0.2`), LangChain Core |
| **Reasoning LLM** | Local-first via Ollama (default `gemma4:4b`); remote providers (OpenAI, Anthropic) are opt-in |
| **Backend API** | FastAPI + Uvicorn, Python 3.11+ |
| **Domain models** | Pydantic v2 |
| **Async job queue** | Redis (GPU-bound tasks dispatched to worker processes) |
| **Relational storage** | PostgreSQL 16 via SQLAlchemy 2 + psycopg 3 |
| **Vector store** | Pluggable (pgvector / Chroma) — RAG retrieval |
| **Object store** | Local filesystem (dev) → MinIO/S3 (production) |
| **Frontend** | Next.js App Router, TypeScript, Tailwind CSS, pnpm |
| **Observability** | LangSmith tracing |
| **Linting / types** | Ruff, mypy |

### Operating principles

1. **Evidence-grounded by default.** Every non-trivial claim carries provenance: which model/tool, which version, which inputs, which references.
2. **Confidence is explicit.** Predictions report calibrated or qualitative confidence and surface the assumptions behind them.
3. **Human-in-the-loop for actionable biology.** Actionable outputs pass through a review gate before being presented as recommendations.
4. **Reproducible runs.** Every answer is backed by a recorded, re-runnable trace with inputs, tool versions, parameters, and outputs persisted and addressable.
5. **Coordinates are sacred.** Assembly, strand, and 0-/1-based conventions are always explicit and validated; silent coordinate errors are treated as critical bugs.
6. **Local-first / private by default.** The reasoning LLM runs locally via Ollama so prompts and sequence data need not leave the deployment. Remote providers are opt-in.
7. **Safe by construction.** Safety classification happens early in the graph, not as an afterthought.
8. **Organism-agnostic.** No capability hard-codes human-only assumptions.

---

## Repository layout

```
CellXP/
├── src/
│   ├── backend/cellxp/         # Python package (import name: cellxp)
│   │   ├── agent/              # LangGraph graph, nodes, subgraphs, state, routing, prompts
│   │   │   ├── graph.py        # top-level graph build + compile
│   │   │   ├── state.py        # AgentState TypedDict
│   │   │   ├── routing.py      # conditional edge logic
│   │   │   ├── nodes/          # input_normalizer, intent_classifier, entity_resolver,
│   │   │   │                   #   risk_classifier, planner, task_selector, evidence_integrator,
│   │   │   │                   #   critic, report_generator, human_review_gate
│   │   │   ├── subgraphs/      # per-capability subgraphs (variant_effect, gwas, crispr,
│   │   │   │                   #   annotation, binding, structure, origami, rag, visualization)
│   │   │   └── prompts/        # markdown prompt templates
│   │   ├── api/                # FastAPI app, routers, middleware, dependencies
│   │   │   └── routers/        # variants, gwas, crispr, binding, annotations, structure,
│   │   │                       #   artifacts, runs, chat, visualizations, health
│   │   ├── services/           # external service clients + domain logic
│   │   │   ├── alphagenome/    # AlphaGenome client, schemas, plots, transforms
│   │   │   ├── binding/        # motif scanning, footprinting, delta tracks
│   │   │   ├── crispr/         # guide design, on-target/off-target scoring, base/prime editing
│   │   │   ├── gwas/           # GWAS Catalog, Open Targets, LD, fine-mapping, QTL
│   │   │   ├── origami/        # scaffold routing, staple design, cadnano export
│   │   │   ├── rag/            # retriever, PubMed, vector DB, citation, claim extraction
│   │   │   ├── reference/      # reference genome, annotations, liftover
│   │   │   ├── structure/      # protein/NA structure, DNA shape, contact maps, nucleosome
│   │   │   └── visualization/  # genome browser, GWAS locus plots, contact maps, motif logos
│   │   ├── domain/             # canonical domain types (GenomicInterval, Variant, EvidenceItem),
│   │   │                       #   enums, errors, sequences, safety, validators
│   │   ├── storage/            # SQLAlchemy models, repositories, vector store, object store, cache
│   │   ├── jobs/               # Redis job queue, GPU worker, task dispatch
│   │   ├── cli/                # CLI entry points (run_agent, render_graph, seed_demo_data)
│   │   └── config/             # settings (pydantic-settings), logging, paths
│   └── frontend/               # Next.js App Router (TypeScript)
│       ├── app/                # pages: /, /chat, /runs/[runId], /artifacts/[artifactId]
│       ├── components/
│       │   ├── chat/           # ChatPanel, ChatMessage, ChatInput, ToolCallTimeline
│       │   ├── genome/         # GenomeBrowser, TrackViewer, GeneModelTrack, VariantTable
│       │   ├── plots/          # ContactMapHeatmap, GwasLocusPlot, DeltaTrackPlot, MotifLogo
│       │   ├── structure/      # StructureViewer3D, DnaShapeTrack
│       │   ├── workspace/      # WorkspaceLayout, ArtifactPanel, EvidencePanel, RunInspector
│       │   └── ui/             # Button, Card, Dialog, Tabs
│       └── lib/                # API client, streaming, artifact helpers, types
├── specs/                      # implementation-driving contracts (source of truth)
│   ├── product/                # mission, requirements (FR-*/NFR-*/CR-*), personas, user stories
│   ├── agent/                  # state schema, graph spec, routing/tool-use/evidence/review policies,
│   │   ├── nodes/              #   per-node specs
│   │   ├── capability-subgraphs/  # per-capability subgraph specs
│   │   └── control-flow/       #   run lifecycle, pause/resume, concurrency, replanning
│   ├── biology/                # per-capability I/O, models, transforms; supported species/assays
│   ├── services/               # per-service contracts (alphagenome, gwas, crispr, llm, …)
│   ├── interface/              # API contracts, chat interface, streaming protocol, artifact model
│   ├── data/                   # storage, provenance, audit log
│   ├── evaluation/             # testing strategy, eval plan, golden sets, rubrics
│   ├── training/               # post-training (SFT/DPO/RLVR) — offline track
│   └── planning/               # roadmap, future-additions, milestones, open questions, risks
├── documentation/
│   ├── explanation/            # architecture overview, multi-agent, safety model, evidence &
│   │                           #   confidence, coordinate systems, task patterns, why LangGraph
│   ├── adr/                    # architectural decision records (numbered)
│   ├── reference/              # external models & services catalog, API, CLI, config, env vars
│   ├── guides/                 # how-to guides
│   ├── tutorials/              # step-by-step tutorials
│   └── community-notes/        # practical caveats and field knowledge
├── .agents/
│   ├── onboarding.md           # agent session start guide (read this first)
│   └── guidelines/             # implementation patterns: langgraph, langchain, deepagents,
│                               #   langsmith, interactive-visualization, testing, changelog
├── tests/                      # pytest unit / integration / e2e
├── evals/                      # golden queries, rubrics, regression sets
├── infra/                      # deployment infrastructure
├── notebooks/                  # exploratory notebooks
├── scripts/                    # utility scripts
├── docker-compose.yml          # postgres, redis, ollama (local dev)
├── pyproject.toml              # Python package config + tool config (ruff, mypy, pytest)
├── Makefile                    # dev targets (see below)
└── CONTRIBUTING.md             # extension points and contribution guide
```

---

## Getting started

### Prerequisites

- Conda (the development environment pins Python 3.13)
- NVM/Corepack (the frontend pins Node 22.9.0 and pnpm 10.17.0)
- Docker (for Postgres, Redis, Ollama)

### 1. Start infrastructure

```bash
docker compose up -d
# Pull the default reasoning model into Ollama:
docker compose exec ollama ollama pull gemma4:4b
```

### 2. Create the development environments

```bash
conda env create -f environment.yml
conda activate cellxp

nvm use
corepack enable
pnpm --dir src/frontend install --frozen-lockfile
```

If the Conda environment already exists, synchronize it with
`conda env update -n cellxp -f environment.yml --prune`.

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env as needed. Defaults connect to docker compose services.
# To use a remote LLM instead of Ollama, set OPENAI_API_KEY or ANTHROPIC_API_KEY.
```

### 4. Run the backend API

```bash
make dev-api
# → http://localhost:8000
```

### 5. Run the frontend

```bash
make dev-frontend
# → http://localhost:3000
```

### 6. Run the GPU/async worker (for structure prediction and other heavy jobs)

```bash
make worker
```

### Other Makefile targets

| Target | What it does |
|---|---|
| `make test` | Run pytest |
| `make lint` | Ruff lint check |
| `make typecheck` | mypy type check |
| `make frontend-build` | Build the production Next.js frontend |
| `make eval-smoke` | Validate golden-query JSONL catalogs |
| `make render-graph` | Render the LangGraph agent graph to a PNG |

---

## Domain models

The canonical positioned types live in `src/backend/cellxp/domain/models.py`. Coordinates are **always** 0-based half-open `[start, end)` internally; edge formats are converted before construction. Assembly + organism are always explicit — silent coordinate errors are treated as release blockers.

```python
from cellxp.domain.models import GenomicInterval, Variant

interval = GenomicInterval(
    species="homo_sapiens", assembly="GRCh38",
    chrom="chr17", start=7_674_220, end=7_674_820,
)

variant = Variant(
    chrom="chr17", pos=7_674_420,
    ref="G", alt="A", assembly="GRCh38", rsid="rs28934578",
)
```

---

## Roadmap (summary)

The project is working through three milestones in sequence:

- **M1 (Now):** Foundation contracts (`domain/`, `agent/state`, `services/base`, storage/provenance), core orchestration spine (normalizer → intent → risk → entity → planner), reference genome service (GRCh38 + ≥1 prokaryote), variant-effect vertical slice end-to-end, frontend M1 (chat + streaming + genome browser), safety M1 (risk classifier + audit log).
- **M2 (Next):** GWAS/QTL, RAG/literature grounding, structure prediction, composed evidence pattern (variant → GWAS → fold → report).
- **M3 (Next):** CRISPR design + human-review gate + inverse-design oracle (first composed actionable loop).
- **M4–M5 (Later):** Annotation pipeline, strain optimization/GEM, DNA origami, native macOS app (Tauri), production deployment (GPU pool, MinIO, vLLM).

Full detail in `specs/planning/roadmap.md` and `specs/planning/future-additions.md`.

---

## External models and services

CellXP wraps best-in-class open models rather than building its own. The catalog lives in `documentation/reference/external_models_and_services.md`.

| Task | Model / service |
|---|---|
| Variant effect, binding, annotation | AlphaGenome |
| Sequence-level genomics (any organism) | Evo 2 |
| Protein structure | ESMFold, Boltz-2 |
| Protein design | LigandMPNN, RFdiffusion |
| gRNA scoring (on-target) | Rule Set 3 / Azimuth |
| gRNA scoring (off-target) | CRISPRscan / Cas-OFFinder |
| GWAS associations | GWAS Catalog REST API |
| Target evidence aggregation | Open Targets GraphQL |
| Literature retrieval | PubMed E-utilities |
| DNA nanostructure simulation | oxDNA |
| Origami design export | cadnano |

The reasoning LLM (agent brain) runs locally via **Ollama** (default `gemma4:4b`) and is swappable — set `LLM_PROVIDER`, `LLM_MODEL`, and the appropriate API key in `.env`.

---

## Safety

Safety classification runs early in every graph execution (`risk_classifier` node), before any tool is invoked. Actionable outputs are held behind a `human_review_gate` node. Requests whose primary purpose is hazardous are refused or escalated. The safety model is documented in `documentation/explanation/safety_model.md`; the human-review policy is in `specs/agent/human_review_policy.md`.

---

## Contributing

The system is built to be extended — new capabilities/tasks, models/packages, species/strains, assays, harnesses, artifacts, evals, and community notes/caveats. See `CONTRIBUTING.md` for what each contribution requires and how to make it, and `.agents/guidelines/` for implementation patterns.

Key rules:
- Specs are contracts: change the spec first (or alongside), then the code.
- Safety is non-bypassable: nothing may weaken the early safety gate or the human-review gate.
- Coordinates are sacred: organism + assembly + convention are always explicit.
- Don't change the core agent spine to add a capability — use the service + subgraph pattern.

---

## Names

| Context | Value |
|---|---|
| Python distribution name | `cellxp` |
| Python import package | `cellxp` |
| Product / display name | `CellXP` |
