# DNA Origami Service

> Status: Draft v0.1. Logical service contract for scaffold routing, staple generation, design
> validation, simulation, and cadnano/scadnano export. Impl:
> `src/backend/cellxp/services/origami/`. Methodology: `specs/biology/dna_origami.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §16. All buildable designs are
> actionable and review-gated.

## 1. Purpose

Turn a normalized target geometry and design constraints into an inspectable candidate DNA-origami
design. The service owns geometry normalization, routing-tool selection, scaffold and staple
bookkeeping, constraint validation, optional simulation, and portable design exports. It returns
candidate designs, never an ungated recommendation to build one.

## 2. Operations

```python
class OrigamiService(Service):
    def design(self, request: OrigamiRequest) -> ServiceResult[OrigamiResult]: ...
    def route_scaffold(self, request: RoutingRequest) -> ServiceResult[RoutingResult]: ...
    def generate_staples(self, request: StapleRequest) -> ServiceResult[StapleResult]: ...
    def validate_design(self, request: OrigamiValidationRequest) -> ServiceResult[ValidationResult]: ...
    def simulate(self, request: OrigamiSimulationRequest) -> ServiceResult[SimulationResult]: ...
    def export(self, request: OrigamiExportRequest) -> ServiceResult[ExportResult]: ...
```

`design` composes the other operations. Individual operations remain callable so a replanning loop
can revise geometry, scaffold choice, or constraints without recomputing every prior step.

## 3. Inputs

Requests MUST provide a target shape as a supported parametric shape, 2D wireframe, or 3D mesh plus
explicit physical units. They also carry an optional scaffold sequence or named scaffold, scaffold
length, staple-length and crossover constraints, routing-tool preference, simulation request, and
export formats. If no scaffold is supplied, any default (for example M13mp18) MUST be surfaced in
the request summary and provenance before execution.

The service validates geometry parseability, unit consistency, scaffold alphabet and length,
constraint ranges, and tool-format compatibility. Ambiguous dimensions or consequential missing
constraints produce a clarification upstream; they are not guessed silently.

## 4. Execution

Geometry parsing and basic constraint checks are light operations. Scaffold routing, staple
generation for large designs, oxDNA/CanDo simulation, and complex export validation are heavy and
SHOULD use async jobs. Long-running operations emit `activity.update` liveness events.

Tool selection follows shape class: PERDIX-like tools for 2D wireframes and DAEDALUS/TALOS/ATHENA-
like tools for supported 3D forms. Selection MUST be capability- and license-aware and MUST record
why a tool was chosen. Stochastic tools record their seed; retries never overwrite earlier attempts.

## 5. Outputs & Artifacts

| Output | Artifact type | Actionable | Storage |
|---|---|---:|---|
| layout and scaffold route | `origami` | yes | inline preview + full object |
| staple inventory | `staple_table` | yes | inline top rows + full object |
| validation/QC results | `qc_panel` | yes | inline JSON |
| simulation trajectory/result | `origami_simulation` | yes | object storage |
| cadnano/scadnano design | `file` | yes | immutable object |

Every buildable output has `ArtifactRef.actionable=true`. Exports include a machine-readable design,
a staple sequence table, design/QC metadata, and content hashes. The UI may preview candidates before
review but MUST label them as candidates and withhold recommendation framing.

## 6. Provenance & Confidence

Provenance records normalized geometry and units, routing/simulation tools and exact versions,
scaffold identity and sequence hash, constraints, crossover/staple rules, seeds, export format
versions, and every transformation between tool coordinate systems.

Confidence is a design-quality assessment, not a probability of successful fabrication. It combines
routing completion, constraint satisfaction, staple uniqueness and length distribution, simulation
or mechanical checks when run, and tool applicability. Skipped simulation is an explicit limitation.

## 7. Safety & Review

All returned designs, staple sequences, and build files create `ReviewItem`s under
`specs/agent/human_review_policy.md`. The service cannot approve its own results. A failed critical QC
check prevents recommendation even after review unless the design is revised and revalidated.

## 8. Failure Modes

- unroutable geometry or insufficient scaffold length: no-candidate result with diagnostics;
- unsatisfied staple/crossover constraints: partial candidate marked invalid, never buildable;
- unsupported shape or export format: validation error with supported alternatives;
- simulation timeout/failure: partial result with unvalidated-simulation limitation;
- tool or license unavailable: recoverable `RunError` when another compatible route exists;
- inconsistent tool coordinates: hard integrity error; no export is produced.

## 9. Requirements

- **OGS-1** Every buildable origami artifact and export MUST be actionable and review-gated.
- **OGS-2** Geometry units, scaffold identity/hash, constraints, tool versions, and seeds MUST be
  recorded in provenance.
- **OGS-3** A design MUST pass all configured critical QC checks before it may be framed as buildable.
- **OGS-4** The service MUST distinguish no feasible design, invalid candidate, simulation failure,
  and service failure.
- **OGS-5** Design, staple, and simulation payloads above `OBJECT_INLINE_MAX` MUST use immutable
  object storage.
- **OGS-6** Exported files MUST be round-trip validated against their declared format version.

## 10. Related

`specs/biology/dna_origami.md` · `specs/agent/capability-subgraphs/origami.md` ·
`specs/agent/human_review_policy.md` · `specs/services/visualization_service.md` ·
`specs/interface/artifact_model.md` · `specs/data/object_storage.md`.
