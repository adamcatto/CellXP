# ADR-0007 — Retain the LangGraph harness and adopt Qwen3.8 as the quality model

- **Status:** Accepted
- **Date:** 2026-08-22
- **Related:** `documentation/adr/0002-langgraph-supervisor-with-subgraphs.md`,
  `specs/agent/harness_and_context_engineering.md`, `specs/services/llm_service.md`,
  `specs/serving/reasoning_llm_serving.md`,
  `specs/planning/copilotkit_integration.md`

## Context

The current default reasoning-model specification targets a very small local model. That preserves
privacy and easy setup but is not a credible quality ceiling for long-horizon biological synthesis,
reliable tool use, multimodal interpretation, and coding work.

`Qwen/Qwen3.8-27B` is an Apache-2.0 dense multimodal model released on 2026-08-14 with a native
262k context window, controllable reasoning, coding/agent optimization, and OpenAI-compatible tool
calling when served with the Qwen parser. It is a strong self-hostable quality target, but it is not
a lightweight laptop dependency: useful latency and concurrency require quantization or a capable
GPU serving runtime.

Prime Agent and Hermes Agent offer attractive coding/research loops, persistent execution, memory,
and sub-agent patterns. They are complete agent harnesses rather than drop-in model providers.
Replacing CellXP's explicit supervisor with either would introduce a second control plane and make
the safety-first ordering, typed scientific state, deterministic coordinate handling, review gate,
and per-tool provenance harder to enforce. Prime's mutable continual harness and persistent Python
kernel are especially inappropriate as the authority for review-gated biological actions.

## Decision

1. Keep **LangGraph** as the L1/L2 production harness and source of control-flow truth
   (ADR-0002). CopilotKit is a UI/protocol integration, not an orchestrator.
2. Make **Qwen3.8-27B the target quality-tier reasoning model** for GPU workstation/cluster
   deployments after provider and evaluation gates land. Serve it through the existing
   `openai_compatible` provider using vLLM or SGLang with the official Qwen reasoning/tool parsers.
3. Keep the shipped local baseline usable on modest hardware. Do not silently change the current
   no-GPU quickstart to a 27B download. Deployment profiles select the quality tier explicitly and
   the UI displays model/provider before private data leaves the host.
4. Use one loaded Qwen model with **per-role reasoning budgets** before introducing model swapping:
   low/no reasoning for intent/routing, medium for entity resolution and report drafting, high for
   planning/critique and long-horizon synthesis. Record model revision, quantization, serving flags,
   reasoning effort, tokens, and latency on every LLM `Step`.
5. Add an L3 **research/code workspace agent** through the already-sanctioned deepagents seam. It may
   borrow Prime/Hermes patterns—virtual filesystem, persistent scratch state, bounded sub-agents,
   skills, and code execution—but returns only typed, cited results to the supervisor.
6. Code/file/shell tools run in a sandbox with allowlists, budgets, and explicit side-effect review.
   Self-modifying prompts/skills cannot alter immutable safety, coordinate, provenance, or review
   policy. Skill changes are versioned candidates and require evaluation/promotion.
7. Do not expose raw multi-megabyte model or artifact output to the reasoning window. Feed compact
   evidence summaries and artifact handles back into context; the workspace agent reads full
   payloads lazily through audited tools (`CTX-3`, `CTX-4`).

## Evaluation gate

Qwen3.8 becomes a default for a deployment profile only after recorded evals show:

- structured-output and tool-call validity at or above the current provider;
- no regression on safety/refusal and 100% review-gate enforcement;
- improved composed biology and coding-task scores;
- acceptable time-to-first-token and end-to-end latency at the profile's concurrency;
- stable long-context behavior without relying on context-window size as a substitute for
  compaction and selective retrieval.

Hosted frontier models remain opt-in comparison/fallback providers, never a silent privacy fallback.

## Consequences

**Positive**

- The model quality ceiling rises without weakening deterministic scientific and safety boundaries.
- OpenAI-compatible serving keeps Qwen, hosted providers, and future models interchangeable.
- Coding/research autonomy is isolated behind the same audit, budget, and review contracts as
  biological tools.

**Negative / accepted trade-offs**

- A 27B dense model needs explicit hardware profiles and can be slower than a small router model.
- Deep long-horizon work remains a separate, sandboxed L3 path rather than making every chat turn an
  unconstrained coding-agent loop.
- Prime/Hermes improvements must be reimplemented as bounded patterns instead of inherited wholesale.

## Rejected alternatives

- **Replace LangGraph with Prime Agent or Hermes Agent.** Their monolithic loops and mutable memory
  conflict with accepted production invariants and duplicate orchestration.
- **Use Qwen Code as the product harness.** It is a coding interface, not CellXP's typed biological
  supervisor; it may be used as an evaluation client, not the runtime authority.
- **Make Qwen3.8-27B the unconditional laptop default.** This would turn onboarding and latency into
  hardware-dependent failures.
