# LLM Service

> Status: Draft v0.1. The reasoning-LLM provider abstraction. Default backend: **local Ollama**.
> Parent: `documentation/explanation/architecture_overview.md` §2 (LLM providers). Impl:
> `src/backend/cellxp/services/llm/`. Consumers: all LLM-backed nodes (`specs/agent/nodes/*`).

## 1. Purpose

Provide a single, provider-agnostic interface for the agent's **reasoning LLM** — the model that
powers intent classification, risk classification, entity resolution, planning, critique, and report
writing. This is the agent's "brain"; it is **distinct from the domain foundation models**
(AlphaGenome, Evo 2, ESMFold, Boltz-2, …) catalogued in
`documentation/reference/external_models_and_services.md`.

## 2. Why local-first (Ollama)

- **Privacy.** User sequence data and unpublished hypotheses never leave the host by default
  (`NFR-7`); no third-party API sees prompts.
- **Reproducibility.** A pinned local model + parameters makes runs reproducible without external API
  drift (`FR-24`).
- **No-key onboarding.** The system runs offline/self-hosted with zero external credentials.
- **Cost.** No per-token spend for routine orchestration.

**Default model: `gemma4:4b`** — Google's open-weight **Gemma 4, 4B, instruction-tuned**, served via
Ollama. It is small enough to run on a single consumer GPU / modern laptop while handling the agent's
orchestration roles (classification, planning, critique, report drafting). The choice is also
thematic — AlphaG**emma**NOME-A1. For heavier reasoning, scale up the local model or opt into a remote
provider (see §5) without code changes; per-role overrides (§5) let `planner` use a larger model than
`report_writer` if desired.

Higher-capability **remote providers remain pluggable** for users who opt in (see §5).

## 3. Interface (provider-agnostic)

A thin `LLMProvider` abstraction over `langchain-core` message/tool primitives. All callers depend on
this interface, never on a concrete vendor SDK.

- `complete(messages, *, tools?, response_format?, temperature?, max_tokens?) -> Completion`
- `stream(messages, ...) -> Iterator[Delta]` — token streaming for report generation.
- `embed(texts) -> list[Vector]` — optional, for RAG (may delegate to a dedicated embedder).
- Capabilities advertised per provider: `supports_tools`, `supports_json_mode`, `context_window`,
  `streaming`, `max_concurrent` (int — the number of concurrent in-flight calls the underlying
  runtime can serve against the current model; sourced from `OLLAMA_NUM_PARALLEL` for Ollama,
  the configured `--max-num-seqs` for vLLM, the documented account/tier limit for hosted
  providers). Callers (notably the supervisor's sub-agent spawn policy) MUST treat
  `max_concurrent` as a budget: when more LLM-calling sub-agents are requested than slots are
  available, they queue rather than stampede (see
  `specs/serving/reasoning_llm_serving.md` §3.4).

Structured outputs (JSON mode / tool-calls) are used by classifier/planner nodes; the service
validates returned JSON against the caller's Pydantic schema and surfaces parse failures as
recoverable errors.

## 4. Default backend: Ollama

| Aspect | Detail |
|---|---|
| Endpoint | `OLLAMA_BASE_URL` (default `http://localhost:11434`) |
| Model | `LLM_MODEL` — **default `gemma4:4b`** (Gemma 4, 4B, instruction-tuned) |
| Transport | HTTP via `httpx`; native streaming |
| Deployment | local process or `ollama` container (`docker-compose.yml`) |
| Tools/JSON | use model-native tool-calling/JSON mode where available; else a constrained-decoding/prompt fallback |

Model pull/availability is an operational prerequisite (documented in setup), not a runtime
responsibility of the agent.

## 5. Provider selection

`LLM_PROVIDER` selects the backend: `ollama` (default) | `openai` | `anthropic` | `openai_compatible`.
Remote providers read their own `*_API_KEY` / `*_BASE_URL`. Selection is config-only — **no business
logic may hard-code a provider**. Optional per-role overrides (e.g. a stronger model for `planner`
than for `report_writer`) MAY be supported via `LLM_MODEL_<ROLE>` without changing call sites.

## 6. Configuration (env)

```
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gemma4:4b
# remote opt-in (unset by default):
# OPENAI_API_KEY=...
# OPENAI_BASE_URL=...
# ANTHROPIC_API_KEY=...
```

## 7. Reliability & limits

- **Timeouts + retries** with backoff on the provider call; failures are recoverable errors that the
  agent can route around or report (`NFR-6`).
- **Budget.** Token/latency usage counts against the run `Budget` (`state_schema.md` §15); the service
  reports usage per call.
- **Fallback.** If the configured provider is unreachable, optionally fall back to a secondary
  configured provider; otherwise fail the call gracefully with a clear message.
- **Determinism knobs.** Default low temperature for classifier/planner; record model + params in the
  trace for reproducibility.

## 8. Safety & privacy

- Local-by-default keeps prompts on-host; switching to a remote provider is an explicit,
  audit-logged configuration choice.
- The LLM service does **not** make safety decisions on its own — risk classification is a dedicated
  node (`specs/agent/nodes/risk_classifier.md`); the service only executes prompts.
- Prompts/responses for runs MAY be persisted to the trace per the data-retention policy
  (`specs/data/*`); secrets are never logged.

## 9. Open questions

- Default is `gemma4:4b`; confirm its context window is sufficient for planning over long
  inputs, or set a larger Gemma 4 variant as the default ceiling.
- Whether embeddings live here or in a separate embedding service for RAG.
- Per-role model overrides: ship in v1 or defer.

## 10. Related

`architecture_overview.md` §2 · `specs/agent/nodes/*` · `documentation/reference/external_models_and_services.md`
(domain models, distinct from this) · `docker-compose.yml` · `.env.example`.
