# Workspace Interface

> Status: Draft v0.1. Normative UI spec for the **workspace** — the multi-pane container that
> renders a session (`specs/agent/session_types.md`) as a persistent, interactive copilot. The
> session/workspace model (types, defaults, memory, review posture) is owned by
> `session_types.md`; the **live streaming UX** is owned by `streaming_protocol.md`; the **typed
> outputs** are owned by `artifact_model.md`; the **interactive pane paradigm** is owned by
> `interactive_panes.md`. This spec composes them into the screen the user sees.

## 1. Purpose & paradigm

The workspace is what makes CellXP feel like a *biology IDE for a copilot*, not a chatbot. It
composes three durable surfaces — **chat thread**, **pane dock**, and **session sidebar** — into
a single workspace, modeled on the dual-surface UX pioneered by Claude / ChatGPT / Codex /
Claude Code (and the Claude Code macOS app's split chat + code-viewer in particular) but
specialized for **interactive biological work**.

The user is always one step from:

- the **conversation** with the agent (chat),
- the **objects of conversation** (panes — genome tracks, structures, designs, tables, reports),
- the **context** that makes both meaningful (session: organism/assembly defaults, pinned
  entities, prior artifacts, files, run history),
- the **provenance** that makes both auditable (evidence/run inspector panes).

Panes are first-class and persistent: closing a pane does not delete its artifact; reopening
restores viewport state. Chat and panes share a **selection bus** (`interactive_panes.md` §5),
so picking a residue in the structure pane scrolls the sequence pane, highlights the codon on
the genome browser, and lets the user say "score this position" in chat without typing
coordinates.

## 2. Layout

The workspace fills the viewport with three resizable regions:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Top bar:  workspace ▾    session ▾    persona ▾    review queue 🛡  search  │
├──────────────────┬───────────────────────────────────┬───────────────────────┤
│                  │                                   │                       │
│  Session         │        Chat thread                │      Pane dock        │
│  sidebar         │  (streamed message + thinking +   │  (artifacts, viewers, │
│  (workspaces,    │   activity + clarification cards) │   editors, inspector) │
│   pinned entities,                                                           │
│   artifact lib,  │  ▾ Composer (slash, @-mentions,   │  split/tab/dock       │
│   files,         │     drag-drop uploads)            │  per pane manifest    │
│   run history)   │                                   │                       │
│                  │                                   │                       │
└──────────────────┴───────────────────────────────────┴───────────────────────┘
                              status bar: run status • token/job usage • errors
```

- **Default split** (web, ≥ 1280 px): sidebar `280 px` · chat `42 %` · pane dock `flex`. Both
  splits are user-resizable and persisted per session.
- **Pane-empty session.** When no artifact has been produced yet, the pane dock shows a
  session-typed **starter** (e.g. variant-interpretation sessions show a "paste a variant or
  upload VCF" hint; genome-editing sessions show "describe the edit you want to make"). It is
  not a marketing screen.
- **Single-column mode** (< 1024 px viewport, or user toggle): the pane dock collapses to a
  bottom drawer with tabs; chat fills width. Mobile is not a v1 target, but layout MUST gracefully
  degrade.
- **Focus modes.** Cmd/Ctrl-1/2/3 focus sidebar/chat/dock; Cmd/Ctrl-\\ toggles the sidebar;
  Cmd/Ctrl-J toggles the pane dock.

## 3. Session sidebar

A compact navigation column. Four collapsible sections, in this order:

1. **Workspaces (sessions).** List of the user's sessions, grouped by `SessionType` icon, with
   the active one highlighted. Click switches; "+" creates a new session (type picker, with
   inferred default from current chat if any). Search filters by title/organism.
2. **Pinned entities.** `Session.entities` (`session_types.md` §2) — resolved genes,
   proteins, variants, loci, organisms. Click pins it into the next run's normalized inputs;
   right-click unpins. Drag onto chat composer inserts `@entity` reference.
3. **Artifact library.** `Session.artifacts` grouped by type (structures, tracks, tables,
   reports, …) with type icons. Click opens the artifact in the appropriate pane.
4. **Files & scratchpad.** The session's `deepagents` virtual filesystem
   (`session_types.md` §2 `files`, `.agents/guidelines/deepagents.md`). Upload, drag-drop,
   inline-rename. Click a file → opens in the file viewer pane (or the scratchpad editor for
   `.md`).

A footer block shows the session's **defaults card** (organism, assembly, persona, review
posture) with edit affordance — changes affect future runs only (`api_contracts.md` §3).

A separate **run history** panel (toggleable) lists past runs in this session in reverse
chronological order: status, headline, duration, key artifact thumbnails; clicking a run opens
the **run inspector** pane (`interactive_panes.md` §3.5).

## 4. Pane dock

The dock is the workspace's rich surface — the home of every viewer/editor pane defined in
`interactive_panes.md`. It is an IDE-style dock, not a stack of modals.

### 4.1 Dock model

- **Tabs by default.** New panes open as tabs in the dock. Tabs show the artifact's type icon
  and title; revision indicator badges when `artifact.updated` arrives.
- **Splits.** A tab can be dragged to a dock edge to create a horizontal or vertical split
  (up to a 2 × 2 grid). Splits persist per session.
- **Linked splits.** Two panes can be marked **linked** so their viewports synchronize: e.g.
  genome browser ↔ contact map at the same locus; sequence editor ↔ structure viewer at the
  same residue. Linked state is workspace-local.
- **Focus.** One pane is *focused* at a time; keyboard shortcuts target the focused pane.
- **Pinning.** A pane can be pinned so it is not auto-closed when its source run completes (the
  dock auto-closes ephemeral panes when their run ends, unless pinned or actively edited).
- **Re-open.** Closed panes are reopenable from the artifact library, the run inspector, or
  Cmd/Ctrl-Shift-T.

### 4.2 Pane chrome

Each pane carries a uniform chrome:

```
┌─ [icon] Title · revision  ─────────────────── ⤴ pop-out  ↗ link  ⋯  ✕ ─┐
│ ▾ Coordinates: GRCh38 · chr17:43,044,295-43,125,483 · strand +          │
│ ▾ Confidence summary · Provenance · Exports                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                         (pane body — viewer/editor)                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

- Title + revision are the artifact's manifest values.
- Pop-out opens the pane in a separate browser window/tab (same workspace, ephemeral state).
- Link toggles linked-viewport mode with another open pane.
- Coordinates, confidence, provenance, and exports are disclosure groups (collapsed by default
  except coordinates on positioned artifacts).
- Editor panes also carry a **commit affordance** for proposing candidates (`interactive_panes.md`
  §6).

### 4.3 What auto-opens

The agent and the workspace cooperate on pane placement to avoid both "empty dock" and "pane
explosion" failure modes:

- The **first artifact** of a run auto-opens in the dock.
- Subsequent artifacts of compatible types auto-link into existing panes (e.g. additional tracks
  fold into the open genome browser).
- Different types open as new tabs.
- Reports auto-open as a tab and bring referenced artifacts into focus on click (deep-link via
  citation marker → artifact).
- The user can disable auto-open per session.

## 5. Chat surface

The chat is owned by `chat_interface.md` (static surface) and `streaming_protocol.md` (live
behavior). The workspace adds:

- **Thread is session-scoped, not run-scoped.** Multiple turns/runs accumulate in one scrollable
  thread. Each turn shows the user message, the streaming/streamed assistant message, the
  thinking disclosure, activity rows, clarification/review cards, and artifact bubbles.
- **Artifact bubbles → dock.** When an artifact is referenced inline in the assistant's
  message, it renders as a compact card; clicking opens/focuses the corresponding pane in the
  dock rather than blowing up the message body.
- **@-mention and slash autocompletes** read from the session sidebar (entities, artifacts,
  files) and the macro registry (`routing_policy.md`).
- **Interrupt.** A single "stop" affordance on the active run; resumes/clarifications are
  card-driven per `streaming_protocol.md` §7–§8.

## 6. Review queue

The top bar shows a 🛡 review-queue indicator with the count of `ReviewItem`s awaiting
decision across the workspace's runs (`human_review_policy.md`). Opening it lists items with
artifact previews, rationale, risks, and Approve / Reject / Request-changes controls. Items
deep-link to the producing pane.

Sessions with `review_posture = "strict"` (genome editing, strain optimization, DNA nanotech)
show a more prominent indicator and require explicit dismissal of completed items.

## 7. Search

Cmd/Ctrl-K opens a workspace command palette. Scopes:

- **Sessions** (switch / create).
- **Entities** (genes/proteins/variants resolved in this session; reference-service lookup if
  not yet pinned).
- **Artifacts** (this session's library; cross-session search opt-in for privacy).
- **Runs** (recent runs in this session by headline/status).
- **Files** (session filesystem).
- **Macros / capabilities** (insert a slash command).
- **Actions** (focus pane, toggle thinking, open run inspector …).

Search is read-only and never invokes the agent without an explicit user step.

## 8. Persistence & restore

- **Server-durable** (`specs/data/relational_schema.md`): session, runs, messages, artifacts,
  evidence, review state, files. These restore identically on any client.
- **Client-local** (per-session, browser localStorage / file-backed in macOS): pane dock layout,
  per-pane viewport/zoom, sidebar collapsed sections, thinking-expanded preference. These
  restore best-effort and never affect scientific values (`PNS-9`).
- **Resume mid-conversation.** If a run was paused (clarification/review) or interrupted, the
  workspace renders the pending card on next load and the SSE stream resumes via
  `Last-Event-ID` (`api_contracts.md` §8).

## 9. Notifications

Lightweight in-app notifications surface:

- a run completed in a background session,
- a long async job finished and an artifact is ready,
- a review item was added (above a threshold of importance),
- a non-fatal error occurred mid-run.

Notifications are click-through to the corresponding pane/card. They are local-only by default;
desktop/system notifications are an opt-in setting. They MUST NOT contain raw biological
content (`api_contracts.md` §9).

## 10. Native macOS portability

The workspace is built so the future macOS native shell can re-render the same surfaces over
the same REST/SSE wire. Surfaces with platform-equivalent affordances (window splits, command
palette, file-system files, native notifications) MAY use native primitives, but the session,
chat, pane manifest, and selection-bus contracts (`interactive_panes.md` §4–§5) are invariant.
No scientific logic may live only in a platform shell (`API-10`).

## 11. Requirements

- **WSP-1** The workspace MUST render exactly one session at a time per window and MUST NOT
  silently route a run into a different session than the one the user has focused.
- **WSP-2** Pane placement MUST honor `interactive_panes.md` registry + manifest; the workspace
  MUST NOT inline scientific transforms.
- **WSP-3** Cross-pane viewport linking MUST flow through the selection bus
  (`interactive_panes.md` §5); cross-coordinate-frame links MUST surface their transform.
- **WSP-4** The workspace MUST surface pending clarifications and review items prominently and
  MUST NOT allow the user to "miss" a blocking pause (`streaming_protocol.md` §7–§8).
- **WSP-5** Session defaults are advisory; the workspace MUST NOT auto-mutate
  `RunOverrides` without an explicit user action (`api_contracts.md` §3).
- **WSP-6** Pane layout, viewport, and sidebar collapse state are client-local and MUST NOT be
  persisted to the run trace.
- **WSP-7** The workspace MUST gracefully degrade to single-column on small viewports without
  hiding the streaming/clarification/review surfaces.
- **WSP-8** All interactive workspace surfaces MUST be operable by keyboard alone and MUST
  expose live regions for in-flight run state.
- **WSP-9** Notifications, search results, and pane previews MUST NOT include raw biological
  payloads beyond bounded summaries (`API-9`, `streaming_protocol.md` §11).
- **WSP-10** The workspace MUST consume the REST/SSE wire contracts only and MUST be portable
  to a native macOS shell without coupling to web-only primitives in scientific logic.

## 12. Related

`specs/agent/session_types.md` · `specs/interface/chat_interface.md` ·
`specs/interface/streaming_protocol.md` · `specs/interface/artifact_model.md` ·
`specs/interface/interactive_panes.md` · `specs/interface/genome_browser.md` ·
`specs/interface/api_contracts.md` · `specs/agent/human_review_policy.md` ·
`specs/agent/routing_policy.md` (macros) · `.agents/guidelines/deepagents.md`.
