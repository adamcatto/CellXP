# Streaming Protocol & Progressive Disclosure

> Status: Draft v0.1. Defines **what the system streams to the user and how it is surfaced** during a
> run — modeled on the live UX of ChatGPT / Claude / Codex / Claude-Code. Event shapes derive from
> `specs/agent/state_schema.md` §17; transport/wire details are `specs/interface/api_contracts.md`;
> presentation components live in the frontend (`src/frontend/lib/streaming.ts`,
> `app/chat/*`). Interactive clarifications use `state_schema.md` §7 (`Clarification`).

## 1. Goals

- **Live, legible progress.** The user always sees what the agent is doing within ~2 s of a state
  change (`NFR-1`, `success_metrics.md` D4) — never a frozen spinner, even during long GPU jobs.
- **Progressive disclosure.** Show a clean answer by default; let the user expand into reasoning,
  tool calls, evidence, and provenance on demand. Depth is opt-in, not forced.
- **Everything inspectable.** Thinking, intent, tool inputs/outputs, evidence, and artifacts are all
  reachable so the system stays auditable and trustworthy (`mission.md` §5).
- **Interactive, not just output.** The stream can pause to ask the user a question (with options) or
  request review, then resume — the run is a conversation, not a one-shot.

## 2. Transport

A single ordered event stream per run over **SSE** (`text/event-stream`) from the run endpoint;
each event has a `type`, a monotonic `seq`/`id`, the `run_id`, and a typed `data` payload
(`api_contracts.md`). WebSocket is an allowed alternative transport for the same event schema. The
client maintains a local copy of run state and **patches it per event** (by object id) rather than
re-fetching.

The CopilotKit web chat consumes an **AG-UI projection** of this stream through `POST /api/v1/ag-ui`
(`api_contracts.md` §8.1, ADR-0006). AG-UI lifecycle/message/tool/state/interrupt events are a
presentation adapter, not an alternate run log: canonical ordering, replay, artifact identity,
payload limits, and review decisions remain owned by the CellXP run/event contracts.

## 3. Surfaces (channels) in the UI

The stream multiplexes several logical channels into one timeline. Each event `type` targets a
surface:

| Surface | Events | Default visibility |
|---|---|---|
| **Thinking** (reasoning) | `reasoning.delta`, `reasoning.summary` | **collapsed** under a toggle |
| **Activity** (status/tool calls) | `intent.classified`, `activity.update`, `step.started/finished`, `plan.updated`, `subtask.updated` | compact, expandable |
| **Message / Answer** | `message.delta`, `report.delta` | visible, streamed |
| **Artifacts** (visualizations) | `artifact.added`, `artifact.updated` | visible, inline/workspace |
| **Evidence** | `evidence.added` | on demand (citations/provenance) |
| **Clarification** | `clarification.requested` | interactive card (blocks) |
| **Review gate** | `review.requested` | interactive card (blocks) |
| **Errors / lifecycle** | `error.added`, `run.status`, `run.completed` | inline notices |

## 4. Thinking / reasoning stream

Mirrors ChatGPT/Claude/Codex "thinking":

- LLM-backed nodes (`specs/agent/nodes/*`: intent, risk, planning, critique, report) emit
  `reasoning.delta` tokens as they are produced.
- The UI renders these inside a **collapsible "Thinking" disclosure**:
  - **Collapsed by default.** The header shows a live one-liner (e.g. *"Thinking… planning the
    variant→GRN analysis"*) plus an elapsed timer.
  - A **toggle** lets the user expand to read the streamed reasoning tokens as they arrive, and
    collapse again at any time. The user's expand/collapse preference is sticky per session.
  - When the node finishes, the panel **collapses to a short `reasoning.summary`** (1–2 lines); the
    full streamed text remains available behind the toggle.
- **Per-node grouping.** Each reasoning burst is attributed to its node so the user can tell
  planning-thinking from critique-thinking.
- **Ephemerality & privacy.** Reasoning tokens are **presentational and best-effort** (§9): they are
  not required to be persisted with the durable trace, and whether raw reasoning is retained is a
  config/retention choice (`specs/data/*`). Reasoning never contains secrets and never bypasses the
  safety/review gates — it is commentary, not an action.

## 5. Activity & tool-call stream

The agent narrates its work like Claude-Code's tool log:

- `intent.classified` → an activity chip ("Intent: variant effect prediction").
- `plan.updated` → "Planned 3 steps" (expandable to the subtask DAG); revisions show "Re-planning…".
- `step.started` → an activity row with the tool/model and a human label
  ("Calling **AlphaGenome** (variant effect)…"); `activity.update` carries interim status for long
  jobs ("queued", "running 40%").
- `step.finished` → the row resolves with a **collapsible tool-call detail**: input summary, params,
  `tool_version`, and an **output summary/preview**. Full inputs/outputs link to the run inspector
  (`specs/interface/workspace_interface.md`).
- `evidence.added` → adds a citation/evidence chip the user can open for provenance
  (`evidence_and_confidence.md`).

Heavy async steps (GPU/genome-wide) keep emitting `activity.update` so the surface shows liveness
without blocking the answer (`control-flow/concurrency.md` §3).

## 6. Message, answer & artifact streaming

- **Message/answer tokens** stream via `message.delta` / `report.delta` and render incrementally as
  markdown; **citations resolve live** as referenced evidence arrives
  (`report_generator.md`, `evidence_and_confidence.md`).
- **Artifacts/visualizations** stream as: `artifact.added` first emits a **placeholder** (type +
  title + "rendering…"), then `artifact.updated` populates the payload when ready, so a genome track,
  locus plot, structure, or guide table appears progressively (`artifact_model.md`). Large payloads
  are referenced by `storage_ref` and fetched lazily.
- Ordering lets the UI interleave prose and visuals (e.g. "here's the predicted effect" → track →
  continued explanation).

## 7. Interactive clarifications ("ask the user")

When a node emits a **blocking** `Clarification` (`state_schema.md` §7), the run pauses
(`awaiting_input`, `control-flow/pause_and_resume.md`) and the stream sends
`clarification.requested`. The UI renders a **Claude-Code-style question card**:

- The **question** plus a list of **option cards** (`ClarificationOption.label`), with the
  `is_recommended` option highlighted/first (suffix it "(recommended)").
- **Single- or multi-select** per `allow_multiple`.
- A **"yes, and …" / "Other" free-text field** when `allow_freeform=true`: the user can pick an
  option **and** add extra guidance in the same submission (e.g. choose "GRCh38" *and* type "also
  check the mouse ortholog"). Pure free-text ("Other") is also accepted.
- Submitting posts a `ClarificationAnswer { selected_option_ids, freeform }` to the resume endpoint
  (`api_contracts.md`); the run re-enters the emitting node and continues
  (`pause_and_resume.md` §3).

Design rules: ask **only when consequential** and **batch** related questions into one card
(`routing_policy.md` §4, `FR-7`); always offer a sensible default/recommended option so the user can
proceed with one click; keep options mutually intelligible (short labels, detail on hover).

> Example card
>
> > **Which assembly should I use for `BRCA1`?**
> > - GRCh38 / hg38 *(recommended)*
> > - GRCh37 / hg19
> > - T2T-CHM13
> >
> > ☐ *yes, and… (add anything else)* → free text

## 8. Review-gate cards

`review.requested` renders the actionable-biology gate (`human_review_policy.md`): candidate
artifact(s), rationale, risks, and linked evidence, with **Approve / Reject / Request changes**
controls. Like clarifications it blocks (`awaiting_review`) and resumes on decision. Until approved,
actionable output is shown as a **candidate**, never as a recommendation.

## 9. Ordering, resumption & reconnect

- Events are **totally ordered** per run by `seq`; clients apply them in order and ignore duplicates.
- On reconnect the client sends `Last-Event-ID`; the server **replays missed state-backed events**
  (`*.added`, `*.updated`, `status`, deltas needed to rebuild the answer). **Ephemeral** events
  (`reasoning.*`, `activity.update`) MAY be dropped on replay — only their resulting state (e.g. a
  finished step, a reasoning *summary*) is guaranteed.
- Because state is checkpointed (`state_schema.md` §18), a paused run reconnected hours later still
  streams its current state and the pending clarification/review card.

## 10. Cancellation & errors

- The user can **cancel/stop** mid-stream; the API sets `run.status=cancelled`, stops dispatch, and
  the stream closes after a final lifecycle event (`run_lifecycle.md` §4).
- `error.added` surfaces **non-fatal** errors inline while the run continues with partial results
  (`NFR-6`); a fatal error emits `run.status=failed` with a user-facing message.

## 11. What is never streamed

- Secrets/credentials, raw internal prompts beyond the reasoning channel, and object-store keys as
  user-facing content.
- An actionable result presented as "do this" before its review gate is approved (§8).
- Anything blocked by the safety model — a `block` yields a refusal message, not a partial dump
  (`safety_model.md`).

## 12. Open questions

- Reasoning granularity (token vs sentence) and how much to retain vs discard.
- Whether `reasoning.summary` is model-generated or templated per node.
- Default expanded/collapsed state of the Thinking panel per persona (novice vs expert).
- Multi-select clarifications: cap on number of options before switching to a different control.

## 13. Related

`specs/agent/state_schema.md` §7/§17 · `specs/interface/api_contracts.md` ·
`specs/interface/chat_interface.md` · `specs/interface/artifact_model.md` ·
`specs/agent/control-flow/pause_and_resume.md` · `specs/agent/control-flow/concurrency.md` ·
`specs/agent/human_review_policy.md` · `specs/agent/nodes/report_generator.md` ·
`documentation/explanation/evidence_and_confidence.md`.
