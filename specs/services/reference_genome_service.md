# Reference Genome / Annotation Service

> Status: Draft v0.1. Logical service contract for assemblies, sequence retrieval, coordinate
> normalization, liftover, entity resolution, and sequence annotation. Impl:
> `src/backend/cellxp/services/reference/`. Methodology:
> `specs/biology/sequence_annotation.md`, `specs/biology/supported_species.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §7, §8, §15, §17.

## 1. Purpose

Act as the system's source of truth for reference assemblies and positioned biological entities. All
coordinate-dependent capabilities depend on this service for validated sequence extraction and
assembly-aware transforms.

## 2. Operations

```python
class ReferenceGenomeService(Service):
    def resolve_entity(self, request: EntityResolveRequest) -> ServiceResult[EntityResolveResult]: ...
    def get_sequence(self, request: SequenceFetchRequest) -> ServiceResult[SequenceFetchResult]: ...
    def validate_variant(self, request: VariantValidationRequest) -> ServiceResult[VariantValidationResult]: ...
    def liftover(self, request: LiftoverRequest) -> ServiceResult[LiftoverResult]: ...
    def annotate(self, request: AnnotationRequest) -> ServiceResult[AnnotationResult]: ...
    def list_supported_references(self) -> ServiceResult[ReferenceCatalog]: ...
```

`annotate` covers gene models, regulatory features, ncRNA, functional assignments, BGCs, and
organism-specific annotation pipelines.

## 3. Inputs

All positioned requests MUST specify organism and assembly or return a clarification requirement
upstream. The service owns contig-name normalization, circular-contig metadata, reference-allele
checks, and coordinate-convention conversion at service boundaries.

Annotation requests may accept uploaded FASTA/genome objects via `RawInput.file_ref`; uploaded
payloads are read from object storage and linked in provenance.

## 4. Execution

Light operations: entity lookup, sequence extraction, contig normalization, variant validation,
small-interval annotation lookup. Heavy operations: whole-genome annotation, eukaryotic gene finding,
antiSMASH, InterProScan/eggNOG, EC prediction, and large liftover batches.

## 5. Outputs & Artifacts

| Output | Artifact type | Storage |
|---|---|---|
| resolved entities | none or `entity_table` | inline JSON |
| extracted sequence | `sequence_viewer` | inline if small, object if large |
| liftover mappings | `coordinate_table` | inline preview + object |
| annotation features | `genome_track`, `feature_table` | object storage for full feature set |
| exported annotations | GFF/BED/GenBank-like objects | object storage |

## 6. Provenance & Confidence

Every coordinate transform records source assembly, target assembly, convention, tool/database
release, and any failed/unmapped intervals. Annotation confidence records tool-specific score,
database match quality, organism applicability, and whether the feature came from a curated reference
or de novo prediction.

## 7. Correctness Invariants

- Internal interval representation is 0-based half-open.
- User-facing formats retain their native conventions but label them explicitly.
- Circular coordinates are accepted only for assemblies declared circular.
- Ref-allele mismatches are never silently corrected.
- Assembly/species mismatches are validation errors.

## 8. Failure Modes

- ambiguous gene/identifier: return candidates for clarification;
- unsupported organism/assembly: unsupported result with extension guidance;
- missing contig: validation error;
- liftover unmapped region: partial result with unmapped segments;
- annotation pipeline unavailable: recoverable `RunError` and any reference annotations returned.

## 9. Requirements

- **RGS-1** No coordinate-dependent service may bypass reference validation for positioned inputs.
- **RGS-2** Every sequence extraction MUST include organism, assembly, contig, coordinates, strand,
  and content hash in provenance.
- **RGS-3** Liftover and coordinate-convention conversions MUST be recorded as provenance-bearing
  steps.
- **RGS-4** Whole-genome and large annotation outputs MUST use object storage.
- **RGS-5** The service MUST represent circular bacterial references explicitly and support
  origin-crossing sequence extraction.

## 10. Related

`documentation/explanation/coordinate_systems.md` · `specs/biology/sequence_annotation.md` ·
`specs/biology/supported_species.md` · `specs/data/object_storage.md` ·
`specs/interface/genome_browser.md`.
