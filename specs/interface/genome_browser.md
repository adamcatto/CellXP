# Genome Browser

> Status: Draft v0.1. Normative spec for the **genome browser pane** — the canonical interactive
> view of `genome_track`, `locus_plot`, `feature_table`, `coordinate_table`, and `motif_logo`
> artifacts (`artifact_model.md` §4). The pane registers in the workspace's pane registry
> (`interactive_panes.md`) and is composed into the workspace dock
> (`workspace_interface.md` §4). Source data: `specs/services/reference_genome_service.md`,
> `alphagenome_service.md`, `binding_service.md`, `gwas_service.md`, `crispr_service.md`.
> Coordinate invariants: `documentation/explanation/coordinate_systems.md`.

## 1. Purpose

The genome browser is where genomic results become geographic. A user looking at a variant, a
locus, or a regulatory region needs to *see* the position in context: gene models, regulatory
features, conservation, predicted assay effects, binding tracks, GWAS hits, CRISPR guides, and
any user-supplied tracks — all aligned to a stated assembly. It is the most heavily reused
interactive pane in CellXP, and a model for every other pane: typed payloads, explicit
coordinates, progressive loading, accessible fallbacks, bidirectional selection.

## 2. Scope

In scope:

- Display of one or more **tracks** along a linear (or circular) coordinate axis.
- Pan/zoom, locus jump, search, viewport URLs.
- Variant overlay (ref/alt allele rendering).
- Click/hover/select on features, intervals, and individual base pairs at deep zoom.
- Brush a region → emit selection events that trigger downstream actions (re-score, design
  guides, fetch sequence, fetch structure).
- Bidirectional sync with sequence editor, structure viewer, contact map, locus inspector,
  motif logo, and guide/off-target tables (via the workspace selection bus).
- Circular bacterial assemblies and origin-crossing intervals.
- Custom user-uploaded tracks (BED/GFF3/bedGraph) restricted to the session scope.

Out of scope:

- The Manhattan/regional GWAS plot (handled by the **locus inspector** pane, though composed
  into the same dock split).
- 3D contact map heatmap (separate pane; linked viewport).
- The motif PWM editor (separate pane; linked).

## 3. Coordinate model

- **Internal interval representation is 0-based half-open** (matches the reference service,
  `RGS` invariants).
- **Display conventions** match the assembly's native format (1-based inclusive for human-readable
  display, but always labeled with the convention).
- **Assembly + organism + contig + strand + circular** are visible chrome (`workspace_interface.md`
  §4.2). The viewport URL encodes these explicitly:

```
/sessions/{session_id}/panes/genome?org=hsapiens&asm=GRCh38&contig=chr17&start=43044295&end=43125483&strand=+
```

- **Coordinate-frame mismatches** never silently coerce. Dropping a GRCh37 track on a GRCh38
  view requires an explicit recorded liftover (`RGS-3`); the chrome flags the converted track
  as `liftover: hg19 → hg38`.
- **Circular contigs** render as a linear strip with a fold marker; origin-crossing intervals
  draw as two halves with an explicit bridge indicator. A toggle switches to a circular
  layout for small bacterial/plasmid genomes.

## 4. Tracks

### 4.1 Built-in track families

| Family | Artifact source | Default rendering |
|---|---|---|
| Gene model | reference service (`annotate`) | exons/introns/UTRs by transcript, strand-encoded direction |
| Regulatory features | reference service / Ensembl regulation | colored boxes by feature class |
| Conservation | reference service | wiggle/heatmap |
| AlphaGenome assay/tissue delta | `score_variants`/`predict_tracks` | signed wiggle with confidence band |
| Splice score | `score_splicing` | signed wiggle + spliceogenic markers |
| Binding (PWM scan + model) | binding service | colored boxes (motif hits) + wiggle (model occupancy) |
| Accessibility | binding/AlphaGenome | wiggle |
| DNA shape | structure service | wiggle (minor-groove, propeller, …) |
| CRISPR guides + PAMs | crispr service | guide rectangles with PAM tick |
| Off-target hits | crispr service | colored marks; mismatch count encoded |
| GWAS associations | gwas service | points; size = −log10 p, color = trait |
| Variant overlays | variant model / VCF upload | tick + ref/alt indicator |
| Custom user tracks | upload (BED/GFF3/bedGraph) | inferred type or user-chosen |

### 4.2 Track model

```python
class TrackDescriptor(BaseModel):
    id: str                                  # stable; matches artifact id where applicable
    artifact_id: str | None = None
    title: str
    family: TrackFamily
    coordinate_frame: CoordinateFrame        # organism/assembly/contig/strand/circular
    visible: bool = True
    height_px: int                           # user-resizable
    color: str | None = None                 # user override; never the only encoding
    confidence_band: bool = False
    transform_notes: list[str] = []          # e.g. "liftover hg19 → hg38"
    storage_ref: str | None = None           # for tiled fetch
```

- Tracks are reorderable by drag.
- The track header carries a confidence summary, a "view as table" link (`ART-6` fallback), and
  a per-track export menu (BED/GFF3/bedGraph/PNG/SVG).
- A "compare" mode stacks ref vs alt (or condition A vs B) wiggle tracks with their signed
  difference auto-computed and rendered as a third track.

## 5. Interactions

### 5.1 Pan & zoom

- Wheel / pinch zooms around the cursor; drag pans.
- Double-click zooms in 2× around the cursor; shift-double-click zooms out 2×.
- Numeric input (top chrome) accepts `chr17:43044295-43125483`, `BRCA1`, or `rs28897696` —
  unresolved tokens hit the reference service.
- Min/max zoom bounded by the smallest tile resolution and the contig length.
- At deep zoom (≤ 200 bp viewport), the browser renders **base-level sequence**: the underlying
  bases color-coded, codon boxes for CDS, frame strips, IUPAC ambiguity for variants.

### 5.2 Hover & select

- Hover surfaces a typed tooltip per feature/interval.
- Single-click selects a feature → emits `selection: { kind: 'interval', ... }` on the bus.
- Click on a variant tick emits `selection: { kind: 'variant', ... }`.
- Brush selects a region → emits an interval selection; the bus may propagate it to the
  sequence editor (extract sequence) and the structure viewer (if a mappable CDS overlaps).
- Right-click on a feature opens a context menu with capability-targeted actions:
  - *Score this variant with AlphaGenome*
  - *Design CRISPR guides here*
  - *Fold this CDS's protein*
  - *Scan motifs in this window*
  - *Add to candidate edit pool* (genome editing sessions)
  - *Copy locus URL*
  - *Export selection as BED/FASTA*

Each action is a templated turn the user can edit before sending; nothing dispatches silently.

### 5.3 Sequence-level editing

- At base resolution, the browser exposes a thin **edit affordance**: select a base or run of
  bases → "propose substitution / insertion / deletion" — opens the **sequence editor pane**
  (`interactive_panes.md` §3.1) anchored to that interval. Edits never mutate the reference;
  they create a candidate artifact (`interactive_panes.md` §6).

## 6. Variant overlay

- Variants from the run (`Variant` objects, VCF uploads, GWAS hits) render as ticks above the
  base track at the appropriate position.
- A click expands a small inline summary: ref/alt, allele frequency (if known), CADD/AlphaGenome
  score badge, GWAS trait list.
- The bus broadcasts the variant selection to the locus inspector (which centers its Manhattan
  view), to the binding pane (which scores the ref/alt motif delta), and to the structure
  viewer (which highlights the affected residue if a CDS is in frame).

## 7. Loci, gene jump & deep links

- The top chrome's search box resolves entities through the reference service: gene symbols,
  Ensembl/RefSeq IDs, UCSC accession, rsIDs, region strings.
- Ambiguous symbols (e.g. `MYC` across species without a session organism) surface a clarification
  popover — never silent disambiguation (`FR-7`).
- Deep links carry full coordinate context; opening a link in a different session that does
  not have the assembly raises a visible "missing assembly" warning and offers the closest
  liftover.
- A session-scoped **bookmarks** list pins loci for one-click recall.

## 8. Performance & tiling

- Track data uses the artifact tile API (`api_contracts.md` §7 `/artifacts/{id}/tiles`) keyed by
  `(contig, start, end, resolution)`. Resolution is chosen from the viewport zoom (powers of 2);
  clients prefetch one viewport in each direction.
- The renderer is Canvas-first for dense wiggle/heatmap families and SVG for sparse feature
  families; both share the coordinate scale.
- Per-family LOD: at low resolution, gene models render as bars; mid-zoom adds exon structure;
  deep zoom adds codons and base sequence.
- A pane MUST render its viewport from the bounded preview before tiles arrive
  (`PNS-7`, `ART-2`); loading state is per-track, not per-pane.
- Server-side fallback (`visualization_service.md` §4) provides PNG/SVG for accessibility and
  for clients that cannot render Canvas-heavy tracks.

## 9. Accessibility

- Every visible track MUST ship a **table view** (the `ART-6` fallback) accessible from the
  track header.
- A **summary mode** describes the viewport in plain text ("BRCA1 region, GRCh38 chr17:43,044,295–
  43,125,483, 4 tracks visible, 12 features, 1 variant").
- Color is never the sole encoding: feature classes also carry shape/label; signed wiggle uses
  position above/below baseline; categorical track colors carry textual legends.
- All interactions are keyboard-reachable: arrow keys pan, `+`/`-` zoom, `g` opens search,
  `Tab`/`Shift+Tab` walk features, `Enter` selects, context menu via menu key.
- Reduced-motion mode disables zoom animation and morphs.
- Live region announces viewport changes when triggered by selection bus events (e.g. "browser
  jumped to chr17:7,675,160 for variant rs28934578").

## 10. Provenance & evidence

- Every track in the pane links to its source artifact and producing run/subtask/step
  (`ART-1`); the track header's provenance disclosure surfaces tool, version, parameters, and
  any liftover transform (`PROV-1`).
- Predicted tracks (AlphaGenome deltas, binding occupancy) render confidence bands or alpha
  overlays per `evidence_and_confidence.md`; conflicting evidence between tracks is rendered
  visibly, never silently averaged (`evidence_integration.md`).
- User-uploaded custom tracks include an explicit "user upload" badge and are not treated as
  curated evidence in downstream evidence integration unless the user pins them as such.

## 11. Custom user tracks

- Upload via the workspace files panel (`workspace_interface.md` §3) or drag-drop onto the
  pane.
- Supported formats: BED, BED+, GFF3, bedGraph, narrowPeak; large files use tile generation in
  the visualization service.
- Uploads are session-private (`api_contracts.md` §4); filenames are display metadata, never
  paths.
- A user track with mismatched assembly prompts liftover; declining the liftover hides the track
  from the active viewport but keeps it in the library.

## 12. Composition with other panes

The browser is the hub of the workspace's biological geography. Default composition rules
(workspace can override):

- Opening a `structure_3d` artifact that maps to a CDS within the current viewport links
  residue selection between the two panes.
- Opening a `contact_map` for the current contig opens a linked-viewport split with the contact
  map.
- Opening a `motif_logo` opens a small floating pane that highlights motif hits in the viewport
  and follows the brush.
- Opening a `guide_table` filters its rows to the visible interval by default; selecting a row
  jumps the viewport.

Composition NEVER bypasses coordinate-frame checks; cross-frame links require a recorded
transform (`PNS-3`).

## 13. Requirements

- **GBR-1** The browser MUST display explicit organism/assembly/contig/strand/circular chrome
  for every viewport.
- **GBR-2** Cross-assembly track display MUST require a recorded liftover transform; silent
  coercion is forbidden (`RGS-3`).
- **GBR-3** All track payloads MUST be sourced from `artifact_model.md`-compliant artifacts;
  the pane MUST NOT read storage directly.
- **GBR-4** Selection events MUST flow through the workspace selection bus
  (`interactive_panes.md` §5); cross-frame selections MUST surface their transform.
- **GBR-5** Every track MUST offer an accessible table fallback and an underlying-data export
  (`ART-6`, `NFR-9`).
- **GBR-6** Predicted-track confidence and conflicting evidence MUST be visually distinct from
  curated reference tracks.
- **GBR-7** Circular bacterial assemblies MUST be representable as both linear-with-fold and
  circular layouts; origin-crossing intervals MUST not be dropped.
- **GBR-8** Pan/zoom/select MUST be keyboard-operable; an alternative summary text view MUST
  describe the current viewport.
- **GBR-9** User-uploaded custom tracks MUST be session-scoped, untrusted in label rendering
  (`ART-10`), and badged distinct from curated tracks.
- **GBR-10** Right-click actions MUST templated-prefill into the composer or open a confirmation
  card; the browser MUST NEVER dispatch a tool/agent action without explicit user submission.

## 14. Open questions

- Track-library curation: which curated tracks ship by default per organism (gene model only?
  add ENCODE/Ensembl reg?), and how to lazy-load them without exploding the dock.
- Whether to ship a built-in **Hi-C / contact map mini-rail** under the linear tracks as a
  shortcut to opening the contact map pane.
- Resolution autopilot: do we cap base-level rendering hard at 200 bp, or expose it as a user
  preference?
- Cross-organism comparison view (e.g. human ↔ mouse ortholog): in v1 (Strain Optimization
  sessions might want this) or v2.

## 15. Related

`specs/interface/interactive_panes.md` · `specs/interface/workspace_interface.md` ·
`specs/interface/artifact_model.md` · `specs/interface/api_contracts.md` ·
`specs/services/reference_genome_service.md` · `specs/services/alphagenome_service.md` ·
`specs/services/binding_service.md` · `specs/services/gwas_service.md` ·
`specs/services/crispr_service.md` · `specs/services/visualization_service.md` ·
`documentation/explanation/coordinate_systems.md` ·
`documentation/explanation/evidence_and_confidence.md` ·
`.agents/guidelines/interactive-visualization.md`.
