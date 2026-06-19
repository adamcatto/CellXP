# Interactive Panes

> Status: Draft v0.1. Defines the **interactive viewer/editor pane paradigm** that distinguishes
> CellXP from chat-only assistants. Panes are typed, rich, persistent surfaces — bidirectionally
> linked to the chat and to each other — through which the user *sees, edits, and re-runs*
> biological work. Data contract: `artifact_model.md`. Wire/streaming: `api_contracts.md`,
> `streaming_protocol.md`. Composition into the workspace: `workspace_interface.md`. Producer:
> `specs/services/visualization_service.md`. Guidelines:
> `.agents/guidelines/interactive-visualization.md`.

## 1. Why panes (paradigm)

ChatGPT, Claude, and Claude Code prove that a streaming chat thread plus a rich side surface
(canvas, code viewer, artifact pane) is dramatically more useful than chat alone for non-trivial
work. CellXP takes this further because **biology is intrinsically spatial and structural**:
genomes have coordinates, proteins have geometry, networks have topology, and edits are
local interventions whose downstream consequences must be *seen*. A chat answer that says "the
variant disrupts a GATA1 motif" is fine; a chat answer next to a genome-browser pane that
zooms to the locus, draws the motif, animates the ref→alt allele swap, and shows the
AlphaGenome ATAC delta updating in real time is the difference between *being told* and
*understanding*.

The product surface is therefore: a chat thread on one side, and **one or more interactive
panes** on the other, where the agent populates panes as artifacts arrive, the user can drive
panes interactively, and edits in a pane round-trip back into the agent's evidence stream.

## 2. Definitions

- **Pane** — a typed, persistent UI surface bound to one or more `Artifact`s
  (`artifact_model.md`). A pane has its own dock position, viewport state, selection, and edit
  buffer. Panes are reopenable from any artifact ID and survive reconnects.
- **Viewer pane** — read-only inspection of an artifact (e.g. genome track, locus plot, contact
  map).
- **Editor pane** — user can mutate the artifact's *interpretation* (no scientific value changes:
  filter, sort, viewport, selection) **or** propose a **candidate** that supersedes the source
  and triggers re-prediction (sequence edit, structure mutation, origami geometry change,
  guide-pool selection, GRN knockout).
- **Pane host** — the workspace dock that arranges panes (`workspace_interface.md`).
- **Selection model** — the shared, coordinate-aware highlight state that links panes (§5).
- **Candidate** — a derived artifact created by an editor pane action, marked `actionable=true`
  where applicable, that re-enters the agent for re-prediction or review (§6).

## 3. Catalog of panes

Each pane binds to one or more registered artifact types (`artifact_model.md` §4). New panes
MUST be registered with renderer, supported interactions, edit capabilities, accessible
fallback, and the artifact types they consume/produce.

### 3.1 Genomic & sequence panes

| Pane | Binds to | Mode | Notes |
|---|---|---|---|
| **Genome browser** | `genome_track`, `locus_plot`, `feature_table`, `coordinate_table` | viewer + light editor (region select, track toggle, custom user track upload) | canonical pane, see `genome_browser.md`; supports circular bacterial assemblies |
| **Locus inspector** | `locus_plot`, association/coloc tables | viewer | linked Manhattan + LD + gene model; brush → fine-map |
| **Sequence editor** | `sequence_viewer`, raw FASTA/GenBank, gene/CDS context | **editor** | DNA/RNA/protein; nt/aa edits propose candidate; codon optimization marks; CRISPR PAM overlay; conservation/AF-confidence tracks inline |
| **Variant editor** | `Variant` (`state_schema.md`), reference context | **editor** | edit ref/alt/coords; validates against reference; triggers `score_variants` re-run |
| **Motif logo / TF designer** | `motif_logo` | viewer + light editor (edit PWM columns) | edited PWM rescans genome window or feeds binding model |
| **Off-target track / table** | `off_target_table` | viewer + filter editor | linked to genome browser; filter by mismatch count, seed region |

### 3.2 Structural panes

| Pane | Binds to | Mode | Notes |
|---|---|---|---|
| **3D structure viewer** | `structure_3d` | viewer + light editor (color/representation, hide/show chains, measure) | Mol*-class; per-residue confidence (pLDDT) coloring; chain/residue selection bidirectionally linked to sequence pane |
| **Structure mutator** | `structure_3d` + linked sequence | **editor** | click residue → mutate; choose "re-fold candidate" → triggers `predict_structure` on candidate; side-by-side ref vs candidate diff overlay |
| **Ligand docking pane** | `structure_3d` + ligand (SMILES/CCD) | **editor** | drag-drop ligand, choose pocket, queue `score_ligand_binding` |
| **Design constraints pane** | `structure_3d` + protein design spec | **editor** | sketch hotspots, fixed residues, target motif → queue `design_protein` (RFdiffusion/LigandMPNN); results land as a `protein_design_table` pane |
| **Contact map** | `contact_map` | viewer (heatmap zoom/pan) | click pixel → genomic positions; brush triangle → query 3D contact in linked structure |
| **DNA shape track** | `genome_track` (DNA-shape flavor) | viewer | minor-groove / propeller / roll overlays |

### 3.3 Network & systems panes

| Pane | Binds to | Mode | Notes |
|---|---|---|---|
| **GRN graph** | `feature_table` + edges (regulatory) | **editor** (node knock-out / edge perturb) | force-directed; perturbations queue downstream effect simulation |
| **Metabolic / pathway** | reaction/flux table | **editor** | reaction knockout, media change; queue flux-balance analysis |
| **Pathway-on-genome overlay** | pathway × genome_track | viewer | shows where pathway genes sit on the assembly |

### 3.4 Engineering panes (actionable, review-gated)

| Pane | Binds to | Mode | Notes |
|---|---|---|---|
| **Guide pool designer** | `guide_table` | **editor** (select/deselect, re-order, pool compose) | composes the guide set the user wants to ship; the pool is itself an actionable artifact; gated by `human_review_policy.md` |
| **Origami canvas (2D wireframe)** | `origami` (wireframe) | **editor** (drag-to-shape, scaffold path, constraint edit) | PERDIX-class; live re-route on change; staples inventory pane updates |
| **Origami 3D shape editor** | `origami` (mesh) | **editor** | drag mesh vertices, set thickness/edge constraints; DAEDALUS/TALOS/ATHENA-class targets; simulation pane (oxDNA/CanDo) re-runs on commit |
| **Staple table** | `staple_table` | viewer + light editor (rename, group, export selection) | gated; links to origami canvas selection |
| **Protein design table** | `protein_design_table` | viewer + select-and-promote | promote a candidate row to structure mutator pane |

### 3.5 Evidence, narrative, scratch

| Pane | Binds to | Mode | Notes |
|---|---|---|---|
| **Report viewer** | `report` | viewer | markdown + live citation popovers + featured artifact embeds |
| **Evidence inspector** | `EvidenceItem` (any) | viewer | source, provenance, confidence breakdown, link back to producing step |
| **Run inspector** | run snapshot + steps + errors | viewer | full provenance trace; deep-link to any step |
| **Scratchpad / notebook** | session files (deepagents filesystem) | **editor** | markdown + code cells; user notes the agent can reference next turn |
| **Table editor** | any registered `*_table` artifact | viewer + light editor (sort/filter/annotate, propose corrections) | corrections become evidence items, never silent rewrites |

## 4. Pane manifest

Every registered pane is described by a manifest the workspace consumes to mount it:

```python
class PaneManifest(BaseModel):
    id: str                                # pane registry key, e.g. "genome_browser"
    title: str
    consumes: list[ArtifactType]           # which artifact types this pane can render
    produces: list[ArtifactType] = []      # types this pane can create as candidates
    mode: Literal["viewer", "editor"]
    edit_actions: list[EditAction] = []    # see §6
    selection_kinds: list[SelectionKind]   # what selection coordinates this pane emits/consumes
    coordinate_frame: list[str]            # which CoordinateFrame kinds it handles
    accessible_fallback: Literal["table", "summary", "none"]
    actionable: bool = False               # whether candidates are review-gated by default
    server_assist: list[str] = []          # visualization-service operations it depends on
```

The frontend pane registry (`src/frontend/lib/panes/registry.ts`) is the runtime mirror of this
manifest. Adding a pane MUST: register a manifest, declare its renderer + accessible fallback,
declare its edit-action contracts, and supply a server-side support path in
`specs/services/visualization_service.md` if non-trivial.

## 5. Shared selection model

All panes communicate through a single workspace-scoped **selection bus**. A selection is a
typed coordinate that any pane can emit and any compatible pane can highlight.

```python
class Selection(BaseModel):
    kind: SelectionKind                    # see below
    artifact_id: str | None = None         # source artifact, if any
    coordinate_frame: CoordinateFrame      # organism/assembly/strand/chain etc.
    payload: dict[str, Any]                # kind-specific
```

| `kind` | payload shape | producers | consumers |
|---|---|---|---|
| `interval` | `{contig, start, end, strand?}` | genome browser, locus inspector, contact map | genome browser, locus inspector, sequence editor (extracts seq), structure viewer (if mappable) |
| `variant` | `{contig, pos, ref, alt}` | locus inspector, variant editor, table | genome browser (jump+overlay), variant editor, AlphaGenome score panel |
| `residue` | `{chain, resi, insertion?}` | structure viewer, sequence editor | structure viewer, sequence editor (if linked CDS) |
| `motif_hit` | `{contig, start, end, strand, pwm_id, score}` | binding pane, genome browser | motif logo (zoom to PWM), genome browser |
| `node` | `{graph_id, node_id}` | GRN graph, pathway pane | annotation table, expression overlay |
| `staple` | `{design_id, staple_id, indices}` | origami canvas, staple table | origami 3D editor, staple table |
| `row` | `{table_id, row_id}` | any table | corresponding row-source pane |

**Coordinate transforms.** When a selection crosses frames (e.g. residue in chain A ↔ codon in
gene X ↔ interval on GRCh38), the workspace asks the reference service
(`specs/services/reference_genome_service.md`) to resolve the mapping. The mapping is recorded
as a provenance-bearing transform (`PROV-1`) and surfaced to the user before being used
silently for any consequential action. Mismatched frames (wrong organism/assembly) raise a
visible warning, never a silent coercion (`API-10`).

**Visibility & multi-select.** A pane MAY ignore a selection it cannot render. Multi-select is
supported per `kind`; the bus stores an ordered list. Selection state is workspace-local and
ephemeral; it is not persisted to the run.

## 6. Editor panes: candidate model

An editor pane never mutates a source artifact. Editing produces a **candidate** that
references its source via `supersedes` (`ART-4`) and re-enters the agent:

```
EditAction (in pane) ───▶ candidate Artifact (server-side, content-addressed)
                            │
                            ├── if predictive re-run is needed:
                            │     submit run turn with referenced_artifact_ids=[candidate.id]
                            │     and a templated instruction (e.g. "re-score this variant")
                            │     → new run/subtasks → new derived artifacts → pane updates live
                            │
                            └── if actionable (CRISPR pool, origami build, design promotion):
                                  candidate.actionable=true → ReviewItem → review.requested
                                  the pane labels it CANDIDATE / PENDING REVIEW until decision
```

Edit actions per pane MUST declare:

```python
class EditAction(BaseModel):
    id: str                                # e.g. "sequence_editor.substitute"
    label: str
    inputs: list[str]                      # required selection kinds
    produces: ArtifactType                 # candidate artifact type
    rerun_capability: str | None = None    # which capability subgraph to re-invoke
    actionable: bool = False               # gates downstream framing
    confirms: bool = False                 # user must confirm (e.g. multi-residue mutation)
```

**Closed-loop edits.** Inverse-design loops (`FR-18c`, `architecture_overview.md` §5.1) are the
prime example: a user toggles a hotspot residue in the structure mutator pane, the structure
service re-folds the candidate and the AlphaGenome service re-scores any linked sequence
window, the locus inspector and structure viewer both update, and the user iterates. Each
iteration is its own run with full provenance; the pane shows the iteration history as a small
timeline.

**Edits never bypass review.** A buildable origami design, a CRISPR guide pool, a synthesized
protein candidate — all remain CANDIDATE until `review.requested` is approved. Pre-approval
exports are restricted per `artifact_model.md` §8 and audit-logged.

## 7. Pane lifecycle

1. **Mount.** Agent emits `artifact.added` (`streaming_protocol.md` §6) → workspace consults the
   pane registry → mounts the default pane for the type (or, if the user has a preference for
   this artifact type / session, that one). Mounting is idempotent by `artifact_id`.
2. **Stream-in.** Pane receives placeholder; subscribes to `artifact.updated` events for its
   revision; renders progressively as payload / tiles / derived exports arrive.
3. **Interact.** Pan/zoom/hover/select are local; selection changes publish on the selection bus.
4. **Edit (editor panes only).** An `EditAction` constructs a candidate, posts to the API, and
   the pane enters a "candidate pending" state showing both source and candidate side-by-side
   (or in a diff/morph view) until the re-prediction lands.
5. **Compose.** The user can pin two panes into a synchronized split (`workspace_interface.md`
   §4 dock model), or compose multiple artifacts into a single composite pane via the
   visualization service (`VisualizationService.compose`).
6. **Export.** Pane offers exports declared on the artifact manifest (`ExportDescriptor`); the
   server prepares them with recorded transform parameters.
7. **Unmount.** Closing a pane does not delete the artifact; reopening from the run inspector /
   session artifact library restores viewport state (per-session local storage; not persisted to
   the run).

## 8. Performance & progressive loading

- **Inline first, tile next.** Panes MUST become useful from the bounded `summary`/preview
  before the full payload arrives (`artifact_model.md` §9).
- **Tile/range fetches.** Genome tracks, contact maps, and large tables use the
  `/artifacts/{id}/tiles` endpoint with viewport-driven requests; clients prefetch one viewport
  in each direction.
- **Virtualize tables.** Any table > 1k rows uses windowed rendering; full data is paged from
  the server or fetched via the data export.
- **Lazy 3D.** Structure pane downloads coordinates on mount; large complexes use Mol*'s
  built-in level-of-detail; per-residue confidence is fetched as a side-channel.
- **Edit debounce.** Editor panes batch high-frequency edits (e.g. dragging origami vertices)
  before submitting a candidate; explicit "commit" gates re-prediction.
- **Server-side render fallback.** If the client cannot render a payload (size, missing GPU
  features, accessibility mode), the visualization service produces a PNG/SVG fallback.

## 9. Accessibility

- Every interactive pane MUST ship a tabular and/or summary fallback (`ART-6`, `NFR-9`).
- Color is never the sole encoding of meaning; categorical encodings carry text labels;
  continuous encodings carry scale + units.
- All edit actions are reachable by keyboard; selection bus events are also emitted by keyboard
  navigation.
- Live region announces `artifact.added` / `artifact.updated` with the pane title and a one-line
  summary.
- Reduced-motion mode disables structure morphs and origami animations.

## 10. Security

- Pane content (labels, free-text, uploads) is treated as untrusted; renderers escape /
  sanitize; no payload may execute scripts (`ART-10`).
- Object payloads are fetched through the API with authorization scoped to the owning session;
  raw object keys are never exposed (`API-3`).
- Candidate artifacts created in editor panes inherit the session's authorization scope.
- Actionable pane outputs follow `specs/agent/human_review_policy.md` without exception.

## 11. Native macOS portability

The pane registry, selection bus, and edit-action contract are framework-independent. The
Next.js web client implements them in React; a future macOS shell (Tauri or native AppKit) can
reimplement renderers but MUST consume the same artifact payloads, emit the same selection
events, and produce the same candidate artifacts via the REST API. No pane-specific scientific
logic may live only in a platform UI client (`API-10`).

## 12. Requirements

- **PNS-1** Every registered pane MUST have a manifest (§4) declaring consumed/produced
  artifact types, edit actions, selection kinds, and accessible fallback.
- **PNS-2** Panes MUST consume artifact payloads via `artifact_model.md` contracts and MUST NOT
  reach into storage directly.
- **PNS-3** Cross-pane selections MUST flow through the selection bus (§5) with explicit
  coordinate frames; cross-frame transforms MUST be provenance-bearing.
- **PNS-4** Editor panes MUST produce candidates (`supersedes` the source) and MUST NOT mutate
  source artifacts (`ART-4`).
- **PNS-5** Editor-pane candidates that are actionable MUST be review-gated; the pane MUST label
  them as CANDIDATE / PENDING REVIEW until approved.
- **PNS-6** Every pane MUST ship a tabular or summary accessible fallback (`ART-6`, `NFR-9`).
- **PNS-7** Panes MUST become useful from the bounded preview before the full payload arrives;
  large payloads load via tile/range endpoints (`ART-2`, `API-6`).
- **PNS-8** Pane content MUST be safe to render (escape/sanitize untrusted text; no script
  execution) (`ART-10`).
- **PNS-9** Pane state (viewport, selection, dock position) is client-local and MUST NOT
  contaminate the run trace or AgentState.
- **PNS-10** Pane registry contracts MUST be portable to a native macOS client over the same
  REST/SSE wire (`API-10`).

## 13. Related

`specs/interface/artifact_model.md` · `specs/interface/streaming_protocol.md` ·
`specs/interface/api_contracts.md` · `specs/interface/workspace_interface.md` ·
`specs/interface/genome_browser.md` · `specs/interface/chat_interface.md` ·
`specs/services/visualization_service.md` · `specs/services/reference_genome_service.md` ·
`specs/agent/state_schema.md` §10 · `specs/agent/human_review_policy.md` ·
`.agents/guidelines/interactive-visualization.md`.
