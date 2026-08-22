# Skill, Plugin, and Policy-Hook Contract

> Status: Draft v0.1 — **normative contract**. Defines the harness-neutral boundary introduced by
> ADR-0008. RFC-2119 keywords apply. Stable requirement IDs use `SKILL-*`.

## 1. Boundary

CellXP separates four concerns:

1. A **harness adapter** runs the conversational planning/reasoning loop.
2. A **skill plugin** exposes one bounded scientific, research, coding, or workflow operation.
3. The CellXP **policy kernel** authorizes and wraps every invocation independently of the harness.
4. Canonical run storage records steps, evidence, artifacts, interrupts, and final reports.

Qwen Code is the first planned mature harness adapter. LangGraph capability nodes are a temporary
compatibility implementation behind the same skill boundary; graph state is not a public tool
schema.

## 2. Skill manifest (`SKILL-1`)

Every skill MUST publish a stable manifest containing:

- unique `name` and semantic `version`;
- human/model-facing description;
- kind (`capability`, `workflow`, `transform`, `research`, or `coding`);
- JSON schemas derived from Pydantic input and output models;
- side-effect class (`none`, `read`, `write`, or `actionable`);
- whether risk clearance, positioned context, provenance, sandboxing, or review can be required;
- implementation source and immutable implementation/model versions in execution provenance.

The manifest MUST NOT contain credentials, private endpoints, raw sequence data, artifact payloads,
or mutable prompt instructions.

## 3. Bounded invocation (`SKILL-2`)

A skill receives:

- typed arguments validated before execution;
- a kernel-owned context with run/session identity, actor, authorization scope, risk assessment,
  budget, coordinate frame where applicable, and references to approved workspace objects;
- no full transcript, full `AgentState`, arbitrary server filesystem, or unscoped object store.

Large inputs and outputs MUST be addressed by authorized handles (`CTX-4`). A compatibility wrapper
MAY construct legacy graph state internally from the bounded invocation but MUST NOT expose that
state to the model.

## 4. Typed result (`SKILL-3`)

A skill result MUST distinguish success, valid empty, unsupported, recoverable failure, policy
denial, and pending review. It MUST carry typed:

- result data or a durable result reference;
- `Step` records for substantive calls;
- `EvidenceItem` and `ArtifactRef` collections;
- usage/accounting and recoverable errors;
- release state (`releasable` or `awaiting_review`).

An actionable artifact MAY be shown as a candidate with its limitations, but MUST NOT be emitted as
an approved recommendation/export until the canonical review decision permits it.

## 5. Registry and discovery (`SKILL-4`)

Skill registration is append-only per `(name, version)`. Duplicate registration MUST fail. The
registry MAY project manifests to MCP/OpenAI-style tool definitions, but only model-visible skills
that pass deployment policy are published. Internal policy and persistence hooks are never tools.

Harness discovery MUST be scoped by deployment, user authorization, session type, organism/model
applicability, and current run phase. A model MUST NOT receive every installed tool by default.

## 6. Authoritative policy hooks (`SKILL-5`)

The policy kernel runs before and after every skill invocation:

**Before**
- authenticate and authorize the actor/session/object references;
- require a non-blocking risk assessment before biological capabilities;
- validate organism, assembly, coordinate convention, and model applicability where relevant;
- check token, wall-clock, cost, worker, and tool-call budgets;
- constrain filesystem, network, subprocess, and MCP access.

**After**
- validate the result schema and provenance;
- persist Steps/evidence/artifacts before publishing references;
- detect actionable output and set `awaiting_review`;
- redact or replace oversized/private payloads with handles;
- account usage and emit canonical ordered events.

Harness-native hooks SHOULD mirror these checks for low-latency feedback. They MUST NOT be able to
disable, reorder, or override kernel decisions (`HARN-6`).

## 7. Harness adapter (`SKILL-6`)

A harness adapter MUST:

- map canonical session context into bounded harness input;
- map text, plan, tool, progress, artifact, clarification, review, and terminal events back to the
  CellXP run model and AG-UI;
- invoke tools only through the skill executor;
- propagate cancellation and enforce wall-clock/tool-call limits;
- compact context without deleting the durable trace;
- support replay/idempotency and correlate resumes to canonical interrupts;
- run code/shell/file tools in a per-run sandbox.

Adapter-specific memory, skills, hooks, and sub-agent transcripts are advisory workspace state.
Canonical artifacts, evidence, approvals, and audit records remain CellXP-owned.

## 8. Qwen Code profile (`SKILL-7`)

The first adapter targets Qwen Code SDK or headless `stream-json` mode with:

- a pinned Qwen Code release and recorded configuration;
- the self-hosted OpenAI-compatible Qwen3.8 quality profile;
- authenticated MCP/in-process access only to the current run's discovered skills;
- partial streaming events translated to AG-UI;
- explicit loop/tool/wall-clock budgets and loop detection;
- no unrestricted `--yolo`, host shell, host filesystem, or ambient network access;
- CellXP review interrupts rather than generic CLI approval for actionable biology.

Daemon/ACP mode MAY replace single-turn headless processes only after its cancellation, budget,
session-isolation, and reconnect semantics pass contract tests.

## 9. Compatibility migration (`SKILL-8`)

Legacy capability nodes MAY be wrapped as `langgraph_compatibility` workflow skills when:

- their tool-facing input is a bounded Pydantic model;
- the wrapper constructs only the minimal legacy state slice;
- output is converted immediately to `SkillResult`;
- the normal policy kernel surrounds the call;
- parity fixtures compare the wrapped path with the existing graph.

New domain logic MUST land in services/transforms and skill plugins, not directly in the top-level
graph. Deterministic state machines may remain implementation details of a workflow skill.

## 10. Acceptance

- A registry contract test proves duplicate names/versions cannot overwrite each other.
- Invalid tool arguments fail before a worker or legacy node is called.
- Missing/blocked risk assessments prevent biological skill execution.
- An adversarial harness or disabled harness hook cannot bypass kernel policy.
- Actionable outputs remain pending until a canonical review decision.
- Model-facing schemas contain neither graph state nor raw large payloads.
- Every substantive successful invocation has complete Step/evidence/artifact provenance.
- A Qwen Code fixture covers text deltas, tool calls/results, cancellation, failure, and resume.

Kernel/compatibility unit coverage lives in `tests/unit/test_harness_skills.py` and runs without
external services:

```bash
python -m pytest -q tests/unit/test_harness_skills.py
```
