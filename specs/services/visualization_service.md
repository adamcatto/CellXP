# Visualization Service

> Status: Draft v0.1. Logical service contract for converting typed biological results into
> interactive, composable, and exportable artifact payloads. Impl:
> `src/backend/cellxp/services/visualization/`. Presentation contracts:
> `specs/interface/artifact_model.md`, `specs/interface/genome_browser.md`. Capability:
> `specs/agent/capability-subgraphs/visualization.md` (`FR-21`).

## 1. Purpose

Provide the backend data-to-visualization boundary. The service selects a registered artifact type,
normalizes source results into its payload schema, composes compatible views, prepares scalable data
tiles or summaries, and creates export payloads. The frontend owns interaction and rendering; this
service owns data correctness and renderer-independent representation.

## 2. Operations

```python
class VisualizationService(Service):
    def create_artifact(self, request: VisualizationRequest) -> ServiceResult[ArtifactResult]: ...
    def compose(self, request: CompositionRequest) -> ServiceResult[ArtifactResult]: ...
    def prepare_track(self, request: TrackRequest) -> ServiceResult[TrackResult]: ...
    def prepare_structure(self, request: StructureViewRequest) -> ServiceResult[ArtifactResult]: ...
    def export(self, request: ArtifactExportRequest) -> ServiceResult[ExportResult]: ...
    def list_renderers(self) -> ServiceResult[ArtifactTypeCatalog]: ...
```

`create_artifact` chooses and validates a registered payload. `compose` aligns multiple compatible
artifacts while retaining each source's identity, evidence links, coordinate frame, and confidence.

## 3. Inputs

Inputs are typed evidence, service results, existing artifact IDs, or object references plus an
optional requested view/export type. The request MAY specify display intent (compare, overview,
inspect locus), viewport, aggregation, color encoding, and export dimensions, but presentation hints
cannot alter source values.

Positioned data MUST declare organism, assembly, contig, coordinate convention, and strand where
applicable. Molecular structures MUST declare chain/residue mappings. Composition rejects coordinate
or entity-frame mismatches unless an explicit, provenance-bearing transform is supplied.

## 4. Execution & Rendering Boundary

Schema validation, summaries, small transforms, and most vector exports are light. Large track
tiling, contact-map pyramids, structure conversion, and high-resolution export MAY run as async jobs.

The backend emits renderer-independent JSON/data objects and immutable binary payloads. The Next.js
client performs interactive rendering (pan, zoom, hover, selection, confidence toggles). Server-side
rendering MAY produce accessible static previews and PNG/SVG/PDF exports, but MUST use the same
canonical data payload as the interactive view.

## 5. Outputs & Artifacts

The canonical taxonomy is owned by `specs/interface/artifact_model.md`. Core results include
`genome_track`, `locus_plot`, `contact_map`, `motif_logo`, `structure_3d`, typed tables, `origami`,
and `report`. Every result contains an `ArtifactRef`, a schema-versioned payload or `storage_ref`,
source/evidence links, available interactions, export formats, accessibility metadata, and any data
transform notes.

Artifact creation is progressive: emit `artifact.added` with stable ID/type/title and readiness
`pending`, then `artifact.updated` as payloads or derived exports become ready. Updates preserve the
artifact ID and increase its revision.

## 6. Provenance, Confidence & Fidelity

Provenance records all source evidence/artifact IDs, transform code/version and parameters,
coordinate/unit conversions, aggregation or downsampling, color/scale semantics when scientifically
meaningful, and output hashes. Downsampling never replaces the full source object.

Confidence and missingness remain visible data dimensions. The service MUST NOT silently average
conflicting evidence, hide missing values, truncate ranges, or use a scale that changes the sign or
meaning of a biological effect. Any lossy transform is labeled in artifact metadata.

## 7. Actionability & Security

Visualization does not change actionability: an artifact derived from any actionable source remains
actionable and retains its review state. Rendering or export never bypasses a review gate. Text,
labels, and uploaded metadata are treated as untrusted content; payloads cannot inject executable
HTML/script, and object access remains authorization-scoped through the API.

## 8. Failure Modes

- unsupported result/type pairing: validation error with compatible artifact types;
- coordinate/entity-frame mismatch: reject composition or request explicit transform;
- unavailable large payload: recoverable artifact error with source links retained;
- renderer unavailable: valid data artifact with table/static fallback;
- export failure: interactive artifact remains usable and reports export error;
- malformed/untrusted labels: escape or reject without executing content.

## 9. Requirements

- **VZS-1** Every artifact MUST conform to a registered, versioned payload schema.
- **VZS-2** Every artifact MUST link to its producing run/subtask and supporting evidence or source
  artifacts (`FR-29`, `PROV-2`).
- **VZS-3** Positioned artifacts MUST carry explicit coordinate metadata and reject silent frame
  mismatches.
- **VZS-4** Large payloads MUST use object storage and load progressively; event/state payloads stay
  below configured inline limits.
- **VZS-5** All interactive artifacts MUST offer an underlying-data export and an accessible static
  or tabular fallback (`NFR-9`).
- **VZS-6** Lossy transforms, missingness, confidence, and conflicting evidence MUST remain visible.
- **VZS-7** Derived artifacts MUST preserve the strongest actionability/review restriction of any
  source.
- **VZS-8** Artifact payloads and labels MUST be safe to render as untrusted content.

## 10. Related

`specs/agent/capability-subgraphs/visualization.md` · `specs/interface/artifact_model.md` ·
`specs/interface/genome_browser.md` · `specs/interface/streaming_protocol.md` ·
`.agents/guidelines/interactive-visualization.md` · `specs/data/object_storage.md`.
