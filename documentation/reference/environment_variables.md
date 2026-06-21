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
