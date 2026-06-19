# Supported Assays / Output Heads — Reference

> Reference spec for the **assay/readout heads** the prediction models expose — the menu of outputs a
> caller can request (e.g. from AlphaGenome) and how they map to evidence/artifacts. Consumed by
> `variant_effect_prediction.md`, `binding_site_prediction.md`, and the `variant_effect`/`binding`
> subgraphs. Conventions: `specs/biology/README.md`.

## 1. Why assays are explicit

Multimodal models (AlphaGenome) predict **many readouts**; a request selects a subset. Naming them
explicitly lets the agent ask for the right head, resolve tissue/cell-type context, and label evidence
precisely. The concrete, versioned list is pinned per model release in the service
(`services/alphagenome/`); this spec defines the **categories and contract**.

## 2. Assay categories (modalities)

| Category | Example readouts | Typical model | Resolution |
|---|---|---|---|
| Gene expression | RNA-seq / CAGE track, per-gene expression | AlphaGenome | per-tissue/cell-type |
| Chromatin accessibility | ATAC / DNase | AlphaGenome, ChromBPNet | per-tissue |
| Histone marks | ChIP-seq (H3K27ac, H3K4me3, …) | AlphaGenome | per-mark/tissue |
| TF binding | ChIP-seq occupancy | AlphaGenome heads | per-TF/tissue |
| Splicing | donor/acceptor usage, Δ splice score | SpliceAI / AlphaGenome | per-site |
| 3D / contacts | contact maps | Orca | per-locus |
| DNA shape | minor-groove width, roll, … | DNAshapeR | per-base |

## 3. Programmatic contract

```python
class AssaySpec(BaseModel):
    key: str                                 # stable assay id (pinned per model release)
    category: str                            # §2
    model: str                               # producing model key
    organisms: list[str]                     # applicable organism classes (supported_species.md)
    tissue_resolved: bool
    output_kind: Literal["track","scalar","matrix","per_base"]
```

- A request references `assays: list[str]` by `key`; the service validates against the pinned list and
  the organism's applicability (`supported_species.md`).
- Each returned assay → an `EvidenceItem` (claim references the assay+tissue) and/or a track in the
  output artifact; `value` shape follows `output_kind`.
- Unknown/inapplicable assay → validation error with the available set (do not silently substitute).

## 4. Defaults

When `assays` is omitted, the capability uses the model's **default panel** (documented per release).
Tissue/cell-type defaults likewise; if a requested tissue is unavailable, the agent reports the
closest available and notes the substitution.

## 5. Adding a new assay / output head (extension procedure)

New assays appear when a model release exposes more heads, or when a new predictive model is added to
the catalog. Adding one is a **registration + mapping** change, not a change to capability logic.

### 5.1 What a new assay MUST provide

1. **Stable `key`** — a unique, versioned identifier (assay keys are pinned per model release; never
   silently renamed across releases).
2. **`AssaySpec` fields** (§3) — `category`, producing `model`, applicable `organisms` (organism
   classes, `supported_species.md`), `tissue_resolved`, and `output_kind`.
3. **Output mapping** — how the raw model output maps to (a) an `EvidenceItem` claim template and
   (b) an artifact/track type (`artifact_model.md`), with units and the `value` shape for its
   `output_kind`.
4. **Confidence semantics** — what the assay's confidence means / how it's derived
   (`evidence_and_confidence.md`).
5. **Default-panel membership** — whether it's in the model's default panel (§4) or opt-in only.
6. **A golden example** — at least one input→expected-readout fixture for the eval suite.

### 5.2 Roughly how to do it

1. Add the `AssaySpec` to the producing model's **pinned assay list** in its service
   (e.g. `services/alphagenome/`).
2. Define its evidence-claim template + artifact mapping; add units.
3. Decide organism applicability (must be consistent with `supported_species.md`).
4. Add a golden fixture; verify validation rejects it for inapplicable organisms.
5. Update §2 categories if it introduces a new modality; update changelog.

### 5.3 Acceptance for a new assay

- Requestable by `key`; validated against organism applicability (inapplicable → clear error, never
  silent substitution).
- Produces a provenance-complete `EvidenceItem` + correct artifact type with units.
- Golden fixture passes.

> **TODO (revisit during implementation).** The **registry mechanics** for assays — whether the pinned
> per-release list lives in service config, a generated manifest, or `specs/data/*`, and how versioning
> across model releases is tracked — are **not yet decided**. Finalize alongside the
> AlphaGenome/structure services and the data model. Treat §5 as requirements until then.

## 6. Related

`variant_effect_prediction.md` · `binding_site_prediction.md` · `supported_species.md` ·
`specs/interface/artifact_model.md` · `specs/services/alphagenome_service.md` ·
`documentation/reference/external_models_and_services.md` §1/§6 · `CONTRIBUTING.md` (how to
contribute a new assay).
