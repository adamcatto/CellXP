# LangChain Implementation Guidelines

Model abstraction, structured outputs, tools, and messages. Spec: `specs/services/llm_service.md`.
Code: `src/backend/cellxp/services/llm/`, `agent/nodes/*`, `agent/prompts/*`.

## The reasoning LLM goes through one abstraction

- All LLM-backed nodes call the **LLM service** (`llm_service.md`), never a vendor SDK directly.
- Default backend is **local Gemma 4 4B via Ollama**; remote providers are config-only swaps.
- Build chat models from config (provider + model + params). For Ollama use `langchain-ollama`'s
  `ChatOllama(base_url=OLLAMA_BASE_URL, model=LLM_MODEL, temperature=...)`; for remotes use the
  matching `langchain-*` integration. Selection is driven by `LLM_PROVIDER`/`LLM_MODEL`
  (and optional per-role `LLM_MODEL_<ROLE>`).

```python
# services/llm/factory.py (sketch)
def build_chat_model(role: str | None = None):
    provider = settings.llm_provider          # "ollama" | "openai" | ...
    model = settings.model_for(role)          # role override or default
    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(base_url=settings.ollama_base_url, model=model, temperature=0.1)
    ...  # other providers behind the same return type
```

## Structured outputs (prefer over free text)

- Classifier/planner nodes must return **schema-validated** objects, not prose. Use
  `model.with_structured_output(PydanticModel)` so `Intent`, `Plan`, `Clarification`, and tool args
  are typed (`state_schema.md`).
- Validate on the boundary; a parse failure is a **recoverable** error → retry once with a repair
  hint, then degrade (`NFR-6`). Track retry rate (a post-training signal, `post_training.md`).
- Keep temperature low for classification/planning; allow more for report writing.

## Tools

- Domain capabilities are **services**, selected by the agent (`tool_use_policy.md`) — wrap them as
  LangChain tools only where a node genuinely lets the model choose a tool. Most capability dispatch
  is explicit graph routing, not model-chosen tool calls.
- External MCP servers (`mcps/`) can be exposed as tools (e.g. literature/data) — bind them to the
  node/sub-agent that needs them, not globally.

## Messages & prompts

- Prompts are **versioned files** in `agent/prompts/*` (`supervisor.md`, `planner.md`, …), loaded at
  build time — not inline strings (`harness_and_context_engineering.md` §B5).
- Pass **minimal sufficient context** per call (state slice, not whole state); pack evidence
  compactly; always include organism/assembly for positioned reasoning.

## Streaming

- Use streaming for `message`/`report` token deltas and surface reasoning where the provider supports
  it (`streaming_protocol.md`). Map LangChain stream events to our typed SSE events.

## Don't

- Don't hard-code a provider/model anywhere but the LLM service factory.
- Don't accept unstructured LLM text where a schema is expected.
- Don't inline large tool outputs into the prompt — reference them (`deepagents.md`,
  `harness_and_context_engineering.md` §B2).
