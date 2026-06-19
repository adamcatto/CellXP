# ADR-0005 — Human review gate for actionable biology

- **Status:** Accepted (v0.1)
- **Date:** initial safety design
- **Related:** `documentation/explanation/safety_model.md`,
  `specs/agent/human_review_policy.md`, `specs/data/audit_log.md`,
  `specs/agent/nodes/risk_classifier.md`, `specs/agent/nodes/human_review_gate.md`

## Context

A subset of CellXP's outputs are **actionable**: candidate CRISPR guides, base/prime edit
specifications, DNA-origami designs (scaffold routing + staples + cadnano export), candidate
protein/binder designs, and synthesizable sequence outputs. Acted on, they translate into
wet-lab experiments, ordered oligos, edited cells, or built nanostructures. The same outputs
are also, by their nature, the ones that most need human judgment: target choice, off-target
tolerance, organism choice, ethical scope, IRB/IACUC posture, and lab capability all sit
outside what the agent can verify.

CellXP is also dual-use: most CRISPR / origami / protein-design capabilities are general
research tools, not weapons, but the system must NOT be a frictionless path to anything that
warrants more friction. We need a safety posture that is **principled, auditable, and not
defeatable by phrasing or by edit-and-retry**.

Several postures were on the table:

1. **Trust + audit only.** Generate the actionable output, log it, surface a disclaimer.
   Cheap; relies on the user being the right kind of careful; provides no structural friction
   on the producing path; downstream consumers (notes, PDFs, exports) lose the disclaimer
   immediately.
2. **Topical blocklist.** Refuse a fixed set of topics outright (e.g. specific pathogens,
   specific edit targets). Easy to circumvent by paraphrasing; lulls users into thinking the
   absence of refusal is approval; punishes legitimate research adjacent to flagged topics.
3. **Model-level safety alone.** Rely on the reasoning LLM's instruction-following / refusal
   behavior. Inconsistent across providers, fragile to jailbreaks, has no audit trail, and
   cannot reason about wet-lab actionability that the LLM does not see (the actionable
   payload is in a tool result, not the prompt).
4. **Structural review gate on actionable outputs.** Mark certain artifact types as
   `actionable`; the agent surfaces them as **candidates** and pauses (`awaiting_review`) for
   an explicit human decision before they are framed as recommendations, exported, or sent
   downstream. The decision is audit-logged with actor, timestamp, and rationale.

## Decision

Adopt **option 4**: every actionable biological output goes through a structural human-review
gate before it is presented as a recommendation, exported in a build-ready format, or used as
input to a downstream actionable step.

Concretely:

- The set of **actionable artifact types** is enumerated and registered
  (`specs/interface/artifact_model.md` §4 + per-service contracts): currently
  `guide_table`, `off_target_table`, `origami`, `staple_table`,
  `origami_simulation`, `protein_design_table`, and any `structure_3d` produced by a
  generative design call. New actionable types MUST be registered with a review rationale.
- Every actionable artifact is created with `ArtifactRef.actionable=true`; the producing
  service NEVER frames it as a recommendation. The artifact is rendered as a **CANDIDATE**
  with rationale, supporting evidence, risks, and any limitations
  (`specs/interface/interactive_panes.md` §6, `specs/interface/streaming_protocol.md` §8).
- The agent graph contains a **`human_review_gate`** node (`specs/agent/nodes/human_review_gate.md`)
  that pauses the run (`awaiting_review`) until a `ReviewDecisionRequest` is posted via the
  API (`specs/interface/api_contracts.md` §6). Approval / rejection / request-changes are the
  only resumption outcomes.
- **`risk_classifier`** (`specs/agent/nodes/risk_classifier.md`) runs early in every run and
  can promote a run's review posture (`session_types.md`) from `standard` to `strict`,
  expanding the set of outputs that require review.
- **`specs/agent/human_review_policy.md`** is the normative policy for which outputs gate,
  what counts as approval, who can approve in which deployment, and how rejections are
  recorded. It is the contract this ADR sets the direction for.
- Review decisions and refusals are mirrored to **`specs/data/audit_log.md`** with actor,
  timestamp, request_id, and the artifact ID. The audit log is append-only.
- Pre-approval export of actionable artifacts is restricted per
  `specs/interface/artifact_model.md` §8; underlying-data exports may still be allowed for
  inspection but build-ready exports (cadnano JSON for origami, ordering-format CSV for guide
  pools) require approval.

The agent does NOT refuse to design CRISPR guides or fold protein candidates. It produces
them, labels them as candidates, surfaces the evidence and risks, and pauses for the human.
That is the entire point: more friction at the right step, no friction elsewhere.

## Consequences

**Positive**

- The "do this" framing is gated by a deliberate human decision, not by phrasing in a chat
  message. Edit-and-retry does not bypass the gate; the gate is on the artifact, not the
  prompt.
- The audit trail is a structural property of the system: a `ReviewItem` decision is one
  row in the audit log, joinable to the artifact, the producing run, and the user who decided.
- Researchers retain full agency. The agent can still design, simulate, and explain — what it
  cannot do is silently transition from "here is a candidate" to "here is what to build" on
  its own.
- Strict sessions (genome editing, strain optimization, DNA nanotech;
  `specs/agent/session_types.md` §4) default to elevated review posture, so the highest-stakes
  workspaces have the highest baseline of friction.
- Dual-use safety becomes inspectable: an evaluator can ask "did every actionable output get
  reviewed?" and answer it from the audit log (`specs/evaluation/safety_rubric.md`).

**Negative / accepted trade-offs**

- Throughput cost. A run that produces an actionable artifact pauses for human input,
  potentially for hours; the agent's "time to recommendation" includes human latency. We
  accept this — it's the feature, not a bug.
- Approval-fatigue risk. Reviewers exposed to many candidates per day may rubber-stamp. We
  mitigate with: candidate batching (related guides reviewed together), explicit rationale
  and risk surfaces on every card, and reviewer-fatigue metrics in
  `specs/evaluation/safety_rubric.md`.
- Single-user deployments. The user is also the reviewer. The gate still serves: it forces
  a separate, deliberate decision from "produce a candidate" to "treat it as a
  recommendation," and it leaves the audit trail.
- The review queue UI must be unmissable; otherwise pauses become silent stalls. The
  `specs/interface/workspace_interface.md` §6 indicator is required, not optional.

**Out of scope (deliberately not adopted)**

- Refusing entire topics (CRISPR, origami, protein design) outright. We are a tool for
  research; we gate, we don't refuse without cause.
- Auto-approval based on heuristics ("looks safe enough"). The gate is a human decision, by
  design. Heuristics inform the risk surface on the card; they do not approve.
- Model-only safety as the primary mechanism. Useful as defense-in-depth, not as the gate.

## Status notes

We will revisit this if (a) the actionable-artifact catalog grows enough that batched review
patterns dominate (suggesting a workflow refinement rather than a policy change), or (b) a
regulated deployment (clinical, GMP, biocontainment) requires a different gating model —
which we'd add as a session-class on top of, not in place of, this gate.
