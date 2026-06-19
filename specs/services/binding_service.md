# Binding Service

> Status: Draft v0.1. Logical service contract for motif scanning, TF binding, accessibility, and
> occupancy-delta prediction. Impl: `src/backend/cellxp/services/binding/`. Methodology:
> `specs/biology/binding_site_prediction.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §1, §6.

## 1. Purpose

Provide a uniform interface for sequence-level binding evidence: motif hits, TF occupancy, footprint
signals, accessibility predictions, and variant-induced gain/loss of binding sites.

## 2. Operations

```python
class BindingService(Service):
    def scan_motifs(self, request: MotifScanRequest) -> ServiceResult[MotifScanResult]: ...
    def predict_binding(self, request: BindingRequest) -> ServiceResult[BindingResult]: ...
    def score_binding_delta(self, request: BindingDeltaRequest) -> ServiceResult[BindingDeltaResult]: ...
```

`predict_binding` may call motif scanning plus AlphaGenome/ChromBPNet/Evo 2 priors depending on
organism and requested TF set.

## 3. Inputs

Inputs may be sequences, intervals, or a variant plus interval. Coordinate-dependent requests require
organism and assembly. `motif_db` defaults to JASPAR but MUST be version-pinned in provenance.

Mammalian binding heads are human/mouse only. Other organisms use motif scanning plus
organism-appropriate sequence priors where available.

## 4. Execution

Light operations: sequence extraction, motif scanning for small windows, delta post-processing, motif
logo assembly. Heavy operations: base-resolution model inference, genome-scale scans, and batch
variant deltas.

Variant delta mode builds reference and alternate sequences with the same coordinate and strand rules
as the AlphaGenome service.

## 5. Outputs & Artifacts

| Output | Artifact type | Storage |
|---|---|---|
| motif hits | `motif_table`, `motif_logo` | inline preview + object for full table |
| binding/accessibility track | `genome_track` | object storage |
| variant binding delta | `delta_plot`, `genome_track` | object storage |
| TF-specific summary | `score_table` | inline JSON |

## 6. Provenance & Confidence

Provenance records sequence/interval extraction, motif DB name/release, PWM/PFM IDs, p-value
thresholds, model identity/version, and variant allele construction. Confidence reflects motif score,
model applicability, TF/motif specificity, assay relevance, and agreement between motif and model
evidence.

## 7. Failure Modes

- unsupported TF or missing motif: return partial result with explicit skipped TFs;
- variant ref mismatch: validation error;
- no motif hits: valid empty result;
- organism unsupported by model head: fall back to motif scanning or return unsupported;
- model unavailable: recoverable `RunError`, keep deterministic motif evidence if produced.

## 8. Requirements

- **BIS-1** Motif database release and motif IDs MUST be recorded for every motif claim.
- **BIS-2** Mammalian-only binding heads MUST NOT run for unsupported organisms.
- **BIS-3** Binding-delta outputs MUST link ref/alt sequence construction to provenance.
- **BIS-4** Track payloads MUST use object storage.
- **BIS-5** Empty motif/binding results MUST be represented as evidence of no detected signal, not as
  service failure.

## 9. Related

`specs/biology/binding_site_prediction.md` · `specs/services/alphagenome_service.md` ·
`specs/biology/networks_systems_analysis.md` · `specs/interface/genome_browser.md`.
