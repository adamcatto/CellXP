# Chat Interface

> Status: Draft v0.1. Normative spec for the **static chat surface** — layout, composer
> affordances, history rendering, edit/branch behavior, and accessibility. The **live streaming
> behavior** (streamed answer, collapsible thinking, tool-call/activity log, progressive
> artifacts, clarification & review cards) is owned by `streaming_protocol.md`. The chat lives
> inside the **workspace** (`workspace_interface.md`) and shares state with **interactive panes**
> (`interactive_panes.md`).

## 1. Goals

- A **dense, scrollable thread** of session-scoped conversation that a researcher trusts: every
  turn shows what the agent did, what evidence supports it, and what artifacts it produced — all
  reachable in one click.
- A **composer that knows the science**: `@`-mention resolved entities/artifacts/files, `/`
  invoke macros, drag-and-drop uploads, paste-detection for FASTA/VCF/SMILES/PDB content.
- **Conversation, not stenography.** The user can edit prior messages (creating a branch), pin
  turns, and reference earlier artifacts/evidence without copy-pasting.
- **Mirrors the streaming model.** Every chat element corresponds to a typed event/object from
  `streaming_protocol.md` or `state_schema.md`; nothing is render-only.

## 2. Layout

The chat fills the workspace's middle region (`workspace_interface.md` §2). Top-to-bottom:

```
┌───────────────────────────────────────────────────────────────────────────┐
│  Thread header:  session title · organism/assembly chip · "..." menu      │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│              ── older runs (collapsed groups) ──                          │
│                                                                           │
│  ┌─ user turn ─────────────────────────────────────────────────────┐      │
│  │ message text · referenced @entities · uploaded files            │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│                                                                           │
│  ┌─ assistant turn ────────────────────────────────────────────────┐      │
│  │ ▾ Thinking (collapsed)                                          │      │
│  │ ▾ Activity (intent · plan · tool calls · evidence)              │      │
│  │ Message / report stream                                          │      │
│  │ ◇ artifact bubbles → open in dock                               │      │
│  │ ⏸ clarification / review cards (when applicable)                │      │
│  │ ✕ errors (non-fatal inline)                                     │      │
│  └─────────────────────────────────────────────────────────────────┘      │
│                          ⇣ jump to latest                                 │
├───────────────────────────────────────────────────────────────────────────┤
│  Composer (multiline · @ · / · ⌘↵ to send · drag-drop)                     │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Thread is virtualized** for long sessions; older runs collapse to a one-line summary that
  expands on click (full content remains in `state_schema.md`-backed history).
- **Sticky composer** at the bottom; auto-scroll respects user scroll-up intent.
- **Jump-to-latest** affordance when the user has scrolled away during streaming.

## 3. Turn anatomy

Each chat turn maps to `Message` rows (`state_schema.md` §4, `relational_schema.md`).

### 3.1 User turn

- Markdown-rendered message text (escaped, sanitized).
- Inline **chips** for resolved `@entity` mentions (gene, variant, locus, artifact, file). Chip
  click opens the entity/artifact in a pane.
- **Attachments** strip with file thumbnails (`UploadRef`, `api_contracts.md` §4) — click to
  open in the file viewer pane; revoke removes the upload from the run inputs *before* the
  request is sent.
- **Edit / branch** affordance (§7).

### 3.2 Assistant turn

Composed of multiple surfaces, all driven by typed events (`streaming_protocol.md` §3):

- **Thinking disclosure** (collapsed by default) — `reasoning.delta`/`summary`.
- **Activity log** (compact, expandable) — `intent.classified`, `plan.updated`,
  `subtask.updated`, `step.*`, `activity.update`, `evidence.added`.
- **Message body** — streamed markdown (`message.delta` / `report.delta`); citation markers
  resolve live to `evidence_ids` and render as popover-on-hover with provenance.
- **Artifact bubbles** — compact cards for each `ArtifactRef` produced by this turn: type icon,
  title, status, preview thumbnail; click opens/focuses the corresponding pane in the dock
  (`workspace_interface.md` §4.3, `interactive_panes.md` §7).
- **Clarification / review cards** — blocking interactive cards (`streaming_protocol.md`
  §7–§8); the rest of the turn streams below once resumed.
- **Inline non-fatal errors** — `error.added` rendered as a dismissible notice that does not
  break the message body.
- **Footer**: model + provider chip (e.g. "gemma4:4b · ollama"), elapsed time, token/job usage,
  "view run" link to the run inspector pane.

## 4. Composer

The composer is the user's primary input surface. It is a single multiline field with a
toolbar; complexity hides behind affordances rather than chrome.

### 4.1 Send semantics

- Cmd/Ctrl + Enter sends. Plain Enter inserts a newline. Shift+Enter inserts a newline.
- Send is disabled while a previous run is `running` and the user has not requested an explicit
  follow-up; the in-flight run shows the "stop" affordance instead. Multiple turns in flight in
  one session are not allowed in v1.
- A duplicate `client_request_id` returns the original run rather than dispatching twice
  (`api_contracts.md` §5).

### 4.2 Slash commands (`/`)

Open the macro picker (`routing_policy.md`). Each macro shows a one-line description and
required inputs. Selecting a macro inserts a templated turn with placeholders the user fills in.
The macro picker is fuzzy-searchable and scoped by `Session.default_macros` first, then global.

Examples (illustrative; macros live in the registry):

- `/score_variant chr17:43044295 G>A`
- `/design_guides BRCA1 exon 11 base-edit C>T`
- `/build_origami square 100nm`
- `/lit pubmed "GATA1 binding motif erythroid"`

### 4.3 Mentions (`@`)

Open the entity/artifact picker. Sources, in priority order:

1. `Session.entities` (pinned).
2. `Session.artifacts` library.
3. `Session.files`.
4. Reference-service lookup for unresolved gene/protein/variant queries
   (`specs/services/reference_genome_service.md`).

Picking inserts a chip carrying the resolved ID + label; the run treats it as a referenced
artifact/entity (`CreateRunRequest.referenced_artifact_ids` / normalized entity input). Chips
in the composer can be removed; chips in sent messages are read-only.

### 4.4 Uploads (drag-drop & paste)

- Drop a file anywhere on the composer or chat surface → multipart upload to
  `/sessions/{id}/uploads` → returns `UploadRef` → attached to next message.
- Paste-detection: if the user pastes content that parses as FASTA / VCF / PDB / SMILES /
  cadnano JSON, the composer offers "treat as attached input" with the detected kind. If the
  user declines, the content is sent as message text. Detection is heuristic and never silent.
- Per-upload max size enforced server-side (`api_contracts.md` §4); the composer surfaces the
  limit and rejects oversize files locally.
- Uploads are workspace-private; filenames are display metadata only (`api_contracts.md` §4).

### 4.5 Run overrides

A collapsed **overrides** disclosure on the composer lets the user set per-run:

- organism / assembly (defaults from session),
- persona (`personas.md`),
- model / capability hints (advanced),
- budget caps (`state_schema.md` §15).

Overrides apply to the current turn only; persistent changes go through session settings
(`workspace_interface.md` §3).

### 4.6 Composer keyboard shortcuts

| Action | Shortcut |
|---|---|
| Send | ⌘/Ctrl + ↵ |
| New line | ↵ or ⇧↵ |
| Slash menu | `/` at start of token |
| Mention menu | `@` at start of token |
| Upload file | ⌘/Ctrl + U |
| Toggle overrides | ⌘/Ctrl + , |
| Cancel in-flight run | ⌘/Ctrl + . |
| Re-focus composer | `i` (when chat focused, no input) |

## 5. History rendering

- The chat persists in the session-scoped thread; runs are visually grouped with timestamps.
- Older groups collapse to a one-line summary ("3 turns · 4 artifacts · 12 min") and expand on
  click; the full content remains addressable.
- Streaming runs render top-to-bottom as events arrive; finished runs render their final shape
  from the run snapshot (`api_contracts.md` §5) plus replayable events.
- Citation popovers render lazily (`evidence_and_confidence.md`); large artifact previews load
  only when the artifact bubble is in viewport.

## 6. Citations & references

- **Citation markers** in streamed message text (`[12]`, footnote-style or inline `[Evidence]`
  chips) are resolved from the streaming `citation_map` to `evidence.added` events.
- Hovering a citation shows a popover with source, accession/PMID/DOI, retrieval date, and
  confidence (`evidence_and_confidence.md`).
- Clicking opens the **evidence inspector** pane (`interactive_panes.md` §3.5) with the full
  provenance trail.
- Failed/unresolved citations render as a visible warning chip ("citation pending") rather than
  silently disappearing. A run cannot present a fabricated citation (`RAG-3`).

## 7. Edit, branch & retry

- **Edit a user turn** → opens an inline editor on the message; saving creates a **branch**:
  a new conversation thread that forks at that turn. The original thread remains addressable;
  the active branch is shown by default. Multiple branches per turn are allowed.
- **Retry an assistant turn** → re-runs the immediately preceding user turn with the same
  inputs (idempotency-key reset). Useful after a transient error or to sample again on
  nondeterministic outputs; nondeterminism is flagged in provenance (`PROV §7`).
- **Pin a turn** → highlights it in the thread and adds it to the session sidebar's pinned
  list for quick recall.
- **Delete a user turn** is not permitted; corrections are new turns. Audit and provenance are
  append-only (`PROV-3`). The user can request session-level erasure
  (`api_contracts.md` §3 DELETE).

## 8. Thinking & activity rendering rules

(Delegates the protocol to `streaming_protocol.md`; this section is presentation-only.)

- **Thinking** is one disclosure per assistant turn; expanding shows reasoning grouped by node
  (`reasoning.delta` partitioned by emitting node). The user's expand/collapse preference is
  sticky per session.
- **Activity** is a compact column of rows (tool calls + plan revisions); each row expands to
  show input summary, params, tool version, and output preview. Long jobs show liveness
  ("queued", "running 40%", elapsed).
- **Reasoning is presentational**: it MAY not replay on reconnect; only its `reasoning.summary`
  is guaranteed durable (`streaming_protocol.md` §9). The chat MUST handle the
  reasoning-missing case gracefully.

## 9. Errors

- **Non-fatal errors** (`error.added`) inline as dismissible notices within the turn; the run
  continues with partial results (`NFR-6`).
- **Fatal errors** (`run.status = failed`) render a turn-level error card with a user-facing
  message and a "retry" affordance.
- Errors NEVER include secrets, raw prompts, stack traces, or object keys (`api_contracts.md`
  §2, §9).

## 10. Accessibility

- The thread is a true scroll region with semantic headings per turn.
- ARIA live regions announce: streaming message start, artifact added, clarification requested,
  review requested, run completed/failed. Live updates are throttled to avoid screen-reader
  spam.
- All composer affordances are keyboard-reachable; chip removal is keyboard-operable.
- Reduced-motion mode disables typing animations and artifact bubble morphs.
- Color contrast meets WCAG AA in both themes.

## 11. Privacy

- Message bodies, attachments, and resolved entities are private to the session
  (`api_contracts.md` §9).
- Switching the LLM provider to a remote backend surfaces a visible chip in the assistant turn
  footer ("model: gpt-4o · openai") before any private content is sent off-host
  (`llm_service.md` §8).
- Pasted content that detects as a sensitive sequence type prompts a one-time confirmation
  before sending to a remote provider, if one is configured (configurable per session).

## 12. Requirements

- **CHT-1** Every chat turn MUST correspond to durable records in `state_schema.md` (Messages,
  Runs); rendering never invents content.
- **CHT-2** The composer MUST NOT dispatch a run with an in-flight one in the same session;
  duplicate `client_request_id` MUST resolve to the original run.
- **CHT-3** Slash macros and `@`-mentions MUST resolve through registered registries
  (macro registry, session entities/artifacts/files, reference service); the composer MUST NOT
  silently fabricate references.
- **CHT-4** Pasted content classified as a sensitive sequence type MUST surface its
  classification before the message is sent; pasted content MUST NEVER be silently uploaded as
  a file.
- **CHT-5** Citation markers MUST resolve to `EvidenceItem` IDs from the run's `citation_map`;
  unresolved citations MUST be visibly flagged, never hidden (`RAG-3`).
- **CHT-6** Editing a user turn MUST create a branch; it MUST NOT destructively modify a
  prior turn's `Message`/`Run`/audit records (`PROV-3`).
- **CHT-7** Errors surfaced in chat MUST NOT include secrets, raw prompts, stack traces, or
  object keys (`API-10`).
- **CHT-8** ARIA live announcements MUST cover streaming start, artifact added, blocking
  cards, and run completion; updates MUST be throttled.
- **CHT-9** Remote-provider use MUST be surfaced in the assistant turn footer; sensitive
  payloads MUST require explicit confirmation before egress.
- **CHT-10** Composer keyboard model and `@`/`/` autocompletes MUST be portable to the native
  macOS client over the same REST contracts.

## 13. Related

`specs/interface/streaming_protocol.md` · `specs/interface/workspace_interface.md` ·
`specs/interface/interactive_panes.md` · `specs/interface/artifact_model.md` ·
`specs/interface/api_contracts.md` · `specs/agent/state_schema.md` · `specs/agent/routing_policy.md` ·
`specs/agent/personas.md` · `specs/services/llm_service.md` ·
`documentation/explanation/evidence_and_confidence.md`.
