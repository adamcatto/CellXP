# Artifact Model

> Status: Draft v0.1. Normative contract for the typed, addressable outputs rendered in the CellXP
> workspace (`FR-27..29`). Lightweight in-run references derive from `specs/agent/state_schema.md`
> §10; persistence and payload storage are defined by `specs/data/relational_schema.md` and
> `specs/data/object_storage.md`; creation is owned by `specs/services/visualization_service.md`.

## 1. Purpose & Boundary

An **artifact** is a durable, typed view of a run result: a genome track, locus plot, structure,
table, origami layout, report, or downloadable file. It is neither the source evidence nor an
arbitrary component state. The backend owns identity, schema, source links, access, and canonical
data; the frontend owns interactive presentation.

Artifacts MUST be:

- addressable by stable ID and deep link;
- linked to the run/subtask/step and evidence that produced them;
- schema-versioned and renderer-independent;
- progressively loadable without placing large payloads in agent state or SSE;
- exportable as underlying data plus an appropriate visual/document format;
- explicit about coordinates, units, confidence, missingness, and review state.

## 2. Manifest and In-State Reference

`AgentState.artifacts` carries the compact `ArtifactRef`. The artifact API returns the full manifest:

```python
class ArtifactManifest(BaseModel):
    id: str
    schema_version: str                         # manifest schema, e.g. "1.0"
    type: ArtifactType
    payload_schema: str                         # e.g. "cellxp.genome_track/1.0"
    title: str
    description: str | None = None
    status: Literal["pending", "ready", "partial", "failed"]
    revision: int = 0                           # monotonic for artifact.updated

    session_id: str
    run_id: str
    subtask_id: str | None = None
    step_id: str | None = None
    evidence_ids: list[str] = []
    source_artifact_ids: list[str] = []
    supersedes: str | None = None                 # corrected artifact ID (ART-4)

    summary: dict[str, Any] = {}                # bounded inline preview
    payload: dict[str, Any] | None = None        # only when <= OBJECT_INLINE_MAX
    storage_ref: str | None = None               # opaque server-side object key
    content_type: str | None = None
    content_hash: str | None = None

    coordinate_frame: CoordinateFrame | None = None
    units: dict[str, str] = {}
    confidence: Confidence | None = None
    limitations: list[str] = []
    transform_notes: list[str] = []

    interactions: list[Interaction] = []
    exports: list[ExportDescriptor] = []
    accessibility: AccessibilityMetadata
    actionable: bool = False
    review_status: Literal["not_required", "pending", "approved", "rejected",
                           "changes_requested"] = "not_required"
    created_at: str
    updated_at: str
```

This is an additive refinement of `ArtifactRef`: state needs only `id`, `type`, `title`, source
links, preview, `storage_ref`, `actionable`, and creation time. Clients fetch the manifest when a
full renderer needs more data.

## 3. Common Supporting Types

```python
class CoordinateFrame(BaseModel):
    kind: Literal["genomic", "sequence", "structure", "shape", "none"]
    organism: str | None = None
    assembly: str | None = None
    contig: str | None = None
    convention: str | None = None               # internal: 0-based-half-open
    strand: Literal["+", "-", "."] | None = None
    circular: bool = False
    chain_map: dict[str, str] = {}

class Interaction(BaseModel):
    type: Literal["pan", "zoom", "hover", "select", "filter", "sort", "toggle",
                  "link", "measure"]
    target: str | None = None

class ExportDescriptor(BaseModel):
    format: str                                  # png, svg, csv, bed, gff3, mmcif, json, ...
    media_type: str
    kind: Literal["visual", "data", "source"]
    ready: bool = True

class AccessibilityMetadata(BaseModel):
    summary: str                                 # concise non-visual interpretation
    table_available: bool = False
    static_preview_available: bool = False
    keyboard_help: str | None = None
```

Scientific meaning lives in data fields, never color alone. Categorical encodings include labels;
continuous encodings include scale/domain/units; missing and below-detection values are distinct.

## 4. Registered Artifact Types

| Type | Canonical payload | Required exports | Default renderer |
|---|---|---|---|
| `genome_track` | genomic features or numeric intervals | BED/GFF3/bedGraph + SVG/PNG | genome browser track |
| `locus_plot` | variants, associations, LD, genes | CSV/TSV + SVG/PNG | linked locus plot |
| `contact_map` | indexed matrix + labels/resolution | matrix/NPZ + PNG | canvas heatmap |
| `motif_logo` | alphabet + position-weight matrix | MEME/JASPAR + SVG/PNG | sequence logo |
| `structure_3d` | structure object + chain/residue mapping | mmCIF/PDB + PNG | Mol*-class viewer |
| `guide_table` | typed guide/off-target rows | CSV/TSV/JSON | virtualized table |
| `feature_table` | typed annotation/function rows | CSV/TSV/JSON | virtualized table |
| `function_table` | function/domain/EC assignments | CSV/TSV/JSON | virtualized table |
| `protein_design_table` | candidate sequences/scores | FASTA/CSV/JSON | gated table |
| `staple_table` | staple sequences/positions | CSV/FASTA/JSON | gated table |
| `origami` | geometry, scaffold route, staple links | cadnano/scadnano/JSON + PNG | origami layout |
| `origami_simulation` | trajectory/summary/metrics | tool-native + CSV/JSON | simulation panel |
| `sequence_viewer` | sequence + annotations | FASTA/GenBank + text | sequence viewer |
| `coordinate_table` | source/target mappings | BED/TSV/JSON | table |
| `off_target_table` | genomic off-target hits | CSV/BED/JSON | gated table/track |
| `affinity_panel` | ligand poses and affinity values | CSV/JSON + PNG | linked panel |
| `qc_panel` | named checks, severity, evidence | JSON/CSV | status panel |
| `report` | markdown + citation/artifact map | Markdown/PDF/HTML | document viewer |
| `file` | immutable opaque or domain file | original | download/preview |

New types MUST be registered with a payload schema, renderer/fallback, export set, accessibility
behavior, size strategy, and actionability rule. A one-off JSON blob is not a valid artifact type.

## 5. Payload Contracts

Every payload starts with `schema`, `version`, and `data`. Type-specific schemas enforce at least:

- **Genomic payloads:** explicit `CoordinateFrame`; each interval uses internal 0-based half-open
  coordinates; display/export conversion is labeled.
- **Tables:** stable row IDs, typed column descriptors, units, null semantics, server-side paging or
  object-backed full data, and a bounded preview.
- **Matrices:** row/column identity, dimensions, resolution, missing-value marker, scale semantics,
  and multiresolution/object reference for large arrays.
- **Structures:** format, chains, residue mapping, coordinate-file reference, model number, and
  per-residue confidence reference where available.
- **Reports:** markdown, citation marker → evidence ID map, featured artifact IDs, limitations, and
  confidence summary.
- **Files:** original filename, media type, byte size, content hash, and safe-preview capability.

Payload values MUST remain canonical scientific values. Viewport filtering, sorting, coloring, and
selection are client state and do not mutate the artifact.

## 6. Progressive Lifecycle and Versioning

1. Producer reserves a stable artifact ID and persists a `pending` manifest.
2. `artifact.added` sends the compact reference and placeholder.
3. Producer writes/links payload, increments `revision`, and emits `artifact.updated`.
4. Further derived exports or partial data increment `revision`; clients apply only newer revisions.
5. `ready` means the canonical payload is available; export jobs may complete later.
6. `failed` retains source/evidence links and a user-facing error; it is not silently removed.

Artifacts are immutable scientific records. A material data correction creates a new artifact that
references `supersedes`; revisions are only for completing the same logical payload or adding
derived representations. UI preferences never create revisions.

## 7. Composition and Links

A composite artifact lists all `source_artifact_ids` and preserves the strongest review restriction
and every coordinate-frame constraint. Genomic composition requires identical organism/assembly or
an explicit recorded liftover. Selecting an item MAY deep-link to its source evidence, run step,
another artifact, or a synchronized browser viewport.

Artifact URLs use `/sessions/{session_id}/artifacts/{artifact_id}` for workspace context; canonical
API identity remains `/artifacts/{artifact_id}`. Links remain stable if titles or layouts change.

## 8. Export, Access, and Security

- All interactive types provide underlying data plus at least one accessible static/tabular form.
- Export preserves native coordinate conventions and labels any conversion.
- Object keys are never treated as public URLs; clients request authorized content/export URLs from
  the API.
- Filenames and labels are escaped; markdown/HTML is sanitized; artifacts never execute uploaded
  scripts or active document content.
- Actionable artifacts can be previewed as candidates while pending review, but download/export MAY
  be restricted by review policy and is always audit logged.
- The v1 API restricts actionable export until `review_status=approved`; successful exports persist
  a descriptor, immutable content hash, and `side_effect.performed` audit link. Manifest responses
  do not reveal server-side object keys.

## 9. Performance

Inline `summary` and `payload` are bounded by `OBJECT_INLINE_MAX` (default 16 KiB). Larger data use
object storage, lazy retrieval, range/tile requests where appropriate, and virtualization. A
renderer MUST become useful from the preview before the complete payload arrives when the type
supports progressive loading.

## 10. Requirements

- **ART-1** Every artifact MUST have a stable ID, registered type, manifest/payload schema versions,
  producing run/subtask/step links, and supporting evidence or source-artifact links.
- **ART-2** Payloads above `OBJECT_INLINE_MAX` MUST use immutable object storage; agent state and SSE
  carry only references/previews.
- **ART-3** Artifact updates MUST preserve ID and use monotonic revisions; clients MUST ignore stale
  updates.
- **ART-4** Material scientific corrections MUST create a superseding artifact, not mutate history.
- **ART-5** Positioned artifacts MUST carry explicit coordinate frames and reject silent assembly or
  convention mismatches.
- **ART-6** Every interactive artifact MUST offer underlying-data export and a non-visual or static
  accessible fallback (`NFR-9`).
- **ART-7** Confidence, missingness, limitations, and lossy transforms MUST be represented explicitly.
- **ART-8** Derived/composite artifacts MUST preserve source provenance and the strongest source
  actionability/review restriction.
- **ART-9** Artifact content access MUST be authorized against its owning session/run; raw object
  keys MUST NOT be exposed as durable public URLs.
- **ART-10** Untrusted content MUST be escaped/sanitized and MUST NOT execute in a renderer.

## 11. Related

`specs/agent/state_schema.md` §9–§12 · `specs/services/visualization_service.md` ·
`specs/interface/streaming_protocol.md` · `specs/interface/api_contracts.md` ·
`specs/interface/genome_browser.md` · `specs/data/provenance_model.md` ·
`.agents/guidelines/interactive-visualization.md`.
