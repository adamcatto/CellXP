# Interface Specs

The **user-facing surface** of CellXP. Where the agent's typed state, evidence, and artifacts
become a workspace that scientists actually use. The agent runs the science (`specs/agent/*`),
the services produce the data (`specs/services/*`), the persistence layer keeps the receipts
(`specs/data/*`) — the *interface* is how a user perceives, navigates, edits, and intervenes in
all of it.

The shipping target is a **TypeScript Next.js web app first**, with a planned port to a native
**macOS app** (Tauri/Swift) and eventually other native shells. The REST/SSE contracts
(`api_contracts.md`) and JSON artifact/event fixtures are the portability boundary: no scientific
transformation, coordinate logic, or review-decision policy may live in a platform UI client
(`API-9`, `API-10`).

## Read in this order

| Spec | Defines | Why it's first/last |
|---|---|---|
| `api_contracts.md` | HTTP + SSE boundary between FastAPI and clients; sessions, runs, uploads, clarifications, reviews, artifacts, exports | the wire contract — every other spec is built on top |
| `streaming_protocol.md` | what the agent streams during a run (thinking, activity, message, artifacts, clarifications, review) and how it surfaces in the UI | the *live* UX model |
| `artifact_model.md` | the typed, addressable outputs (manifest, payloads, registered types, lifecycle, exports, security) | what gets rendered in panes |
| `interactive_panes.md` | the catalog and contract for **interactive viewer/editor panes** (genome browser, 3D structure, sequence editor, origami canvas, GRN/pathway graph, …) and how they share selection/coordinate state | the *paradigm* that distinguishes CellXP from chat-only tools |
| `workspace_interface.md` | the multi-pane workspace UI: layout, dock model, session switcher, pinned entities/artifacts, scratchpad, run inspector | composes chat + panes into a session |
| `chat_interface.md` | the static chat surface (layout, composer, history, slash/@/upload, message edit, branching) | one half of the workspace; pairs with panes |
| `genome_browser.md` | the genome-browser pane spec (the canonical example of the pane contract) | first-class genomic pane referenced by many capabilities |

## Shared conventions

- **Chat + pane, not chat alone.** Inspired by Claude Code's macOS shell, the workspace is a
  **chat thread alongside one or more rich, independent panes** that the agent populates and the
  user can drive (`interactive_panes.md`). Panes are not modal popovers; they persist, dock, and
  compose like editor panes in an IDE. See `architecture_overview.md` §3.
- **Bidirectional selection.** Selecting a residue, variant, locus, or staple in *any* pane
  highlights it in *every* compatible pane via a shared selection model keyed to artifact IDs +
  coordinate frames (`interactive_panes.md` §5, `artifact_model.md` §3 `CoordinateFrame`).
- **Editing creates a candidate, not a mutation.** Mutating a sequence/structure/geometry/edit
  spec in a pane creates a new candidate artifact that `supersedes` the source (`ART-4`),
  prompts the agent to re-run the relevant predictions, and updates downstream panes when
  results arrive. The original is never overwritten.
- **Actionable artifacts stay candidates until review.** Any edit-pane output that drives wet-lab
  action (CRISPR guides, origami staples, protein designs) is gated by
  `specs/agent/human_review_policy.md`; the pane MUST visibly label candidates and refuse
  recommendation framing until approved (`streaming_protocol.md` §8).
- **Coordinates are explicit on every pane.** Genomic panes show organism, assembly, contig,
  convention, strand; circular bacterial genomes render explicitly
  (`documentation/explanation/coordinate_systems.md`).
- **Progressive disclosure everywhere.** Answer first; reasoning, evidence, provenance, and
  tool-call details are one click deeper (`streaming_protocol.md` §3). Same rule for panes —
  show the headline view; depth (raw data, exports, transforms) is opt-in.
- **Renderer-independent data.** Backend emits canonical JSON/binary payloads; the frontend
  owns interactive rendering. A pane that needs server-side help (heavy tiles, structure conv,
  high-res export) calls the visualization service via the API, never directly into storage
  (`specs/services/visualization_service.md`).
- **Accessible by default.** Every interactive artifact ships an underlying-data export AND a
  static/tabular fallback (`ART-6`, `NFR-9`). Color is never the sole encoding of scientific
  meaning (`artifact_model.md` §3).
- **Privacy-respecting.** Sequence inputs, uploads, prompts, and artifacts are private; logs
  carry IDs and bounded summaries, never raw biological payloads (`api_contracts.md` §9).

## Stack (from `architecture_overview.md` §3)

Next.js (App Router) · TypeScript (strict) · React · Tailwind · local `components/ui/*`
primitives · SSE via `fetch`/`EventSource` (`lib/streaming.ts`) · typed client in `lib/api.ts`
generated from FastAPI's OpenAPI · **Mol\*** for 3D structure · custom Canvas/SVG for genome
tracks · visx / D3 for scientific plots. Code lives in `src/frontend/`. Native macOS port is
planned via a thin shell over the same REST/SSE wire contract (`api_contracts.md` §10).

## Related

`specs/agent/state_schema.md` · `specs/agent/session_types.md` · `specs/services/README.md` ·
`specs/data/README.md` · `documentation/explanation/architecture_overview.md` §3 ·
`documentation/explanation/frontend_backend_boundary.md` ·
`.agents/guidelines/interactive-visualization.md`.
