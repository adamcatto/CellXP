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

Service URLs (`ALPHAGENOME_SERVICE_URL`, `STRUCTURE_SERVICE_URL`, `GWAS_SERVICE_URL`, and
`CRISPR_SERVICE_URL`) select the corresponding independently deployable adapter endpoint.

## GWAS/QTL and CRISPR adapters

| Variable | Default | Purpose |
|---|---|---|
| `GWAS_BACKEND` | `none` | `none`, offline `deterministic`, direct `ebi`, or `http` worker |
| `GWAS_CATALOG_URL` | EBI production URL | GWAS Catalog REST base for `ebi` |
| `EQTL_CATALOG_URL` | eQTL Catalogue v3 | QTL association REST base for `ebi` |
| `GWAS_SERVICE_URL` / `GWAS_SERVICE_TOKEN` | unset | Typed statistical-worker endpoint/auth |
| `GWAS_SERVICE_TIMEOUT_SECONDS` / `GWAS_SERVICE_RETRIES` | `30` / `2` | Bounded HTTP policy |
| `CRISPR_BACKEND` | `none` | `none`, offline `deterministic`, or production `http` worker |
| `CRISPR_SERVICE_URL` / `CRISPR_SERVICE_TOKEN` | unset | Typed scoring/off-target worker/auth |
| `CRISPR_SERVICE_TIMEOUT_SECONDS` / `CRISPR_SERVICE_RETRIES` | `120` / `2` | Bounded HTTP policy |
| `CRISPR_TOOL_REVISION` | `remote` | Worker toolchain revision recorded at the boundary |

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

Domain foundation models are not configured here yet. Their service implementations must define a
pinned source/revision, cache location, hardware requirements, and provenance behavior before a
download key is added; see `.agents/guidelines/setup-scripts.md`.
