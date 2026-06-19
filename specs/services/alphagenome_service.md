# AlphaGenome / Sequence-Model Service

> Status: Draft v0.1. Logical service contract for variant-effect and sequence-foundation-model
> calls. Impl: `src/backend/cellxp/services/alphagenome/`. Methodology:
> `specs/biology/variant_effect_prediction.md`, `specs/biology/inverse_edit_design.md`,
> `specs/biology/binding_site_prediction.md`. Catalog: `documentation/reference/external_models_and_services.md`
> §1, §2, §6, §8.

## 1. Purpose

Wrap AlphaGenome-class and Evo 2-class sequence models behind one stable service boundary so the
agent can score sequence, variant, regulatory, binding, and splice effects without knowing model
runtime details. This service is a domain oracle, distinct from the reasoning LLM service.

## 2. Operations

```python
class AlphaGenomeService(Service):
    def score_variants(self, request: VariantEffectRequest) -> ServiceResult[VariantEffectResult]: ...
    def score_sequences(self, request: SequenceScoringRequest) -> ServiceResult[SequenceScoringResult]: ...
    def predict_tracks(self, request: TrackPredictionRequest) -> ServiceResult[TrackPredictionResult]: ...
    def score_splicing(self, request: SpliceEffectRequest) -> ServiceResult[SpliceEffectResult]: ...
```

`score_variants` is the primary FR-13 operation. `score_sequences` and `predict_tracks` support
annotation, binding, and inverse-design loops. `score_splicing` MAY delegate to SpliceAI when the
model selector chooses a dedicated splice oracle.

## 3. Inputs

Requests consume normalized domain objects from `state_schema.md`:

- `organism` and `assembly` are required for coordinate-dependent calls.
- Variants MUST pass reference-allele validation before model invocation.
- Sequence windows MUST record extraction coordinates, strand, circular wrapping, and padding.
- Assays/tissues MUST be validated against `specs/biology/supported_assays.md`.

The service MUST reject mammalian-only AlphaGenome heads for microbial or otherwise unsupported
organisms. For non-mammalian sequence scoring, Evo 2-class models are the default oracle.

## 4. Execution

Light steps run in-process: coordinate framing, window extraction, allele substitution, track
post-processing, delta computation. Heavy model inference runs through the job layer when it exceeds
the synchronous latency budget (`specs/agent/control-flow/concurrency.md`).

Every model call emits:

- a `Step` with `tool`, `tool_version`, normalized inputs, params, timing, `input_hash`, and
  `output_ref`;
- one or more `EvidenceItem`s for salient model readouts;
- one or more `ArtifactRef`s for track, delta, or table payloads.

## 5. Outputs & Artifacts

Small summaries MAY be inline JSON. Large arrays and track payloads MUST be written to object
storage (`specs/data/object_storage.md`) and referenced by `storage_ref`.

| Output | Artifact type | Storage |
|---|---|---|
| assay/tissue deltas | `genome_track`, `delta_plot` | track arrays in object store |
| sequence scores / embeddings | `score_table` | inline preview + object for full matrix |
| splice scores | `score_table`, `genome_track` | inline top effects + object payload |
| inverse-design oracle batches | no user artifact by default | persisted evidence + cached objects |

## 6. Provenance & Confidence

Provenance MUST identify the concrete model (`alphagenome`, `evo2`, `spliceai`), weights/revision,
assay head, context length, tissue/cell-type, input sequence hash, and any reference assembly
accession. Confidence must be downgraded when the organism, assay, sequence length, or variant class
is near the edge of model support.

## 7. Caching & Idempotency

Deterministic calls SHOULD be cached by `(tool, tool_version, params, input_hash)`. Cache hits still
emit a `Step` marked as cache-backed so the run trace remains complete.

## 8. Failure Modes

- ref allele mismatch: validation error, no inference;
- unsupported organism/model pairing: explicit unsupported result;
- requested assay unavailable: recoverable error plus valid available assays;
- window too long or unavailable contig: actionable validation error;
- model failure: recoverable `RunError`, optional fallback to another registered oracle.

## 9. Requirements

- **AGS-1** The service MUST enforce organism-appropriate model selection.
- **AGS-2** Every call MUST emit complete provenance as defined in `provenance_model.md`.
- **AGS-3** Track-sized outputs MUST use object storage and content hashes.
- **AGS-4** Variant-effect outputs MUST include confidence and at least one evidence item per
  reported salient effect.
- **AGS-5** The service MUST be callable in-process or as a remote endpoint without changing the
  agent subgraph contract.

## 10. Related

`specs/biology/variant_effect_prediction.md` · `specs/biology/inverse_edit_design.md` ·
`specs/services/binding_service.md` · `specs/data/provenance_model.md` ·
`specs/interface/artifact_model.md`.
