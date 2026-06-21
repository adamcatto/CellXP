# Setup Script Maintenance

Use this guideline whenever a dependency, runtime service, model, configuration variable, or
developer prerequisite changes. The goal is that a clean checkout can still be bootstrapped by one
documented command and that rerunning it safely converges an existing checkout.

## Supported entry points

- `scripts/setup.sh` owns local developer bootstrap: `.env`, the Conda environment, the pinned
  Node/pnpm toolchain, Compose infrastructure, and model acquisition.
- `scripts/download_models.sh` owns model acquisition. It currently pulls the default `LLM_MODEL`
  and all configured `LLM_MODEL_<ROLE>` values through Ollama. Domain-model backends remain
  injectable and have no reproducible weight download until their implementations pin a source and
  revision.

Both scripts MUST be idempotent, resolve paths relative to the repository rather than the caller's
working directory, preserve an existing `.env`, reject malformed input, and support `--help` and a
network-free `--dry-run` path. Never embed credentials, accept licenses for a user, or execute an
untrusted `.env` as shell code.

## Update checklist

When code or a feature adds or changes setup requirements:

1. Update the authoritative manifest first (`environment.yml`, `pyproject.toml`, root/frontend
   `package.json`, `.nvmrc`, `docker-compose.yml`, or `.env.example`). Avoid duplicating version
   pins in a script when the tool can consume the manifest directly.
2. Update `scripts/setup.sh` in the same change if the new dependency needs initialization,
   migration, generated assets, a service readiness step, or a new prerequisite. Keep optional
   capabilities behind explicit flags or profiles; do not make large GPU downloads part of the
   default developer setup.
3. Add a model to `scripts/download_models.sh` only when the consuming adapter exists and the model
   source, immutable revision/checksum, license/acceptance flow, cache location, hardware minimum,
   and configuration key are documented. Downloads MUST be resumable/idempotent and MUST verify a
   revision or checksum where the provider supports it. Ollama role models need only a documented
   `LLM_MODEL_<ROLE>` setting because the script discovers them automatically.
4. Synchronize `.env.example`, `documentation/reference/environment_variables.md`, the relevant
   service spec, and `documentation/reference/external_models_and_services.md`. Record model
   identity and revision in runtime provenance; a setup-time download is not sufficient provenance.
5. Update README setup commands and flags, add network-free tests using fake executables, and keep
   live download/GPU smoke tests opt-in (`T7`, `live`/`gpu`). Never download models in default CI.
6. Run `bash -n scripts/setup.sh scripts/download_models.sh`, the setup-script unit tests, and each
   affected script's `--dry-run`. Update `[Unreleased]` in `CHANGELOG.md`.

If a model requires an account, gated license, or manual credential, stop with an actionable message
that names the provider documentation and required environment variable. Do not silently fall back
to a different model.

## Verification

The network-free T1 regression tests live in `tests/unit/test_setup_scripts.py`:

```bash
python -m pytest tests/unit/test_setup_scripts.py
```

Syntax and dry-run checks:

```bash
bash -n scripts/setup.sh scripts/download_models.sh
scripts/setup.sh --dry-run --skip-backend --skip-frontend
scripts/download_models.sh --dry-run --runtime compose
```

The final command requires no running service in dry-run mode. A real model pull is an opt-in live
operation and is deliberately excluded from the default test suite.
