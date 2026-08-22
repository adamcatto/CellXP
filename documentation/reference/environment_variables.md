# Environment Variables

Copy `.env.example` to `.env`, or let `scripts/setup.sh` create it. The bootstrap script preserves
an existing file. Scripts parse only the specific keys they own; `.env` is never executed as shell
code.

## Core runtime

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | Runtime mode |
| `DATABASE_URL` | local PostgreSQL | SQLAlchemy database connection |
| `REDIS_URL` | local Redis DB 0 | Cache and job-queue connection |
| `OBJECT_STORE_URL` | `file:///tmp/cellxp-artifacts` | Artifact object-store backend |
| `RUNTIME_BACKEND` | `local` | `local` test/dev inline mode, `durable` executor mode, or production `queued` API mode |
| `GRAPH_JOB_STREAM` | `cellxp:graph-commands` | Redis Stream for versioned graph commands |
| `GRAPH_CONSUMER_GROUP` | `cellxp-graph-executors` | Consumer group shared by graph executors |

Production API containers use `RUNTIME_BACKEND=queued`; current LangGraph compatibility-executor
containers use `durable`. `GRAPH_*` names are retained wire/config compatibility during the
harness-adapter migration (ADR-0008).
Run `docker compose -f infra/compose/docker-compose.runtime.yml up --build` for the detached local
stack. The API commits run identity before queue dispatch and does not execute LangGraph inline.

Service URLs (`ALPHAGENOME_SERVICE_URL`, `STRUCTURE_SERVICE_URL`, `GWAS_SERVICE_URL`, and
`CRISPR_SERVICE_URL`) select the corresponding independently deployable adapter endpoint.

## Sequence-model workers

| Variable | Default | Purpose |
|---|---|---|
| `ALPHAGENOME_SERVICE_URL` | unset | CellXP-facing AlphaGenome worker URL (image port 8106) |
| `EVO2_SERVICE_URL` | unset | CellXP-facing Evo 2 worker URL (image port 8107) |
| `ALPHAGENOME_API_KEY` | unset | Credential for official AlphaGenome 0.6.1 hosted inference; worker is not ready without it |
| `EVO2_WEIGHT_PATH` | `/models/evo2_7b.pt` | Checksum-verified official Evo 2 7B checkpoint |
| `EVO2_BATCH_SIZE` | `1` | Official SDK sequence-scoring batch size |
| `EVO2_USE_KERNELS` | `0` | Opt in to official Evo 2/Vortex inference kernels |
| `EVO2_EMBEDDING_LAYER` | `blocks.28.mlp.l3` | Pinned SDK layer used for mean-pooled embeddings |
| `CELLXP_*_RUNTIME_FACTORY` | packaged adapter | Optional `module:function` operator override |

The worker images set their packaged factory defaults. Readiness still fails closed when credentials
or checksum-verified weights are absent.

## GWAS/QTL and CRISPR adapters

| Variable | Default | Purpose |
|---|---|---|
| `GWAS_BACKEND` | `none` | `none`, offline `deterministic`, direct `ebi`/`open_targets`, or `http` worker |
| `GWAS_CATALOG_URL` | EBI production URL | GWAS Catalog REST base for `ebi` |
| `EQTL_CATALOG_URL` | eQTL Catalogue v3 | QTL association REST base for `ebi` |
| `OPEN_TARGETS_GRAPHQL_URL` / `OPEN_TARGETS_RELEASE` | public API / `live` | Open Targets endpoint and provenance release |
| `GWAS_SERVICE_URL` / `GWAS_SERVICE_TOKEN` | unset | Typed statistical-worker endpoint/auth |
| `GWAS_SERVICE_VERSION` | `remote` | Expected worker toolchain revision for attestation |
| `GWAS_SERVICE_TIMEOUT_SECONDS` / `GWAS_SERVICE_RETRIES` | `30` / `2` | Bounded HTTP policy |
| `CRISPR_BACKEND` | `none` | `none`, offline `deterministic`, or production `http` worker |
| `CRISPR_SERVICE_URL` / `CRISPR_SERVICE_TOKEN` | unset | Typed scoring/off-target worker/auth |
| `CRISPR_SERVICE_TIMEOUT_SECONDS` / `CRISPR_SERVICE_RETRIES` | `120` / `2` | Bounded HTTP policy |
| `CRISPR_TOOL_REVISION` | `remote` | Worker toolchain revision recorded at the boundary |

The GWAS worker additionally uses `GWAS_WORKER_REVISION`, `GWAS_LD_PANEL_MANIFEST`,
`GWAS_WORKER_TIMEOUT_SECONDS`, `PLINK_EXECUTABLE`, and `RSCRIPT_EXECUTABLE`. See
`infra/gwas/README.md`; production readiness fails if the pinned executables or panel manifest are
missing or drifted.

Remote data/model access is opt-in. `none` preserves honest unsupported outcomes;
`deterministic` is network-free and does not fabricate catalog evidence, genome-wide off-target
coverage, or model predictions.

## Reasoning LLM

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `openai`, `anthropic`, or `openai_compatible` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama HTTP endpoint |
| `LLM_MODEL` | `gemma4:4b` | Default reasoning model |
| `LLM_MODEL_<ROLE>` | unset | Optional per-role model override |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | unset | Opt-in OpenAI-compatible provider settings |
| `ANTHROPIC_API_KEY` | unset | Opt-in Anthropic provider setting |

`scripts/download_models.sh` pulls `LLM_MODEL` and every configured `LLM_MODEL_<ROLE>` when the
provider is Ollama. Remote-provider models are not downloaded. `CELLXP_ENV_FILE` can point the
download script at a non-default env file; `--env-file` takes precedence when selecting that file,
and exported process variables override values read from it.

Domain foundation-model downloads remain opt-in; see `.agents/guidelines/setup-scripts.md`.

## Structure worker

| Variable | Default | Purpose |
|---|---|---|
| `STRUCTURE_BACKEND` | `none` | `none` for honest unsupported results or `http` for worker dispatch |
| `STRUCTURE_DEVICE` | `cuda` | ESMFold device and Boltz accelerator (`cuda` or `cpu`) |
| `STRUCTURE_JOB_TIMEOUT_SECONDS` | `1800` | Hard limit for a Boltz prediction subprocess |
| `MODEL_CACHE_DIR` | `/models` in worker image | Parent of pinned Hugging Face and Boltz caches |
| `ESMFOLD_REVISION` | `75a3841…97a` | Release-pinned ESMFold weights commit; worker rejects drift |
| `BOLTZ_EXECUTABLE` | `boltz` | Executable path/name; invoked as an argv vector without a shell |
| `CELLXP_LIVE_STRUCTURE` | unset | Set to `1` only to enable opt-in T7 GPU smoke tests |

`scripts/download_models.sh --structure {esmfold,boltz2,all}` acquires these domain weights. Boltz is
pinned to package version 2.2.1 in the worker image and runtime provenance.
