# Binding-Site Prediction — Methodology & Programmatic Contract

> Capability: FR-17. Subgraph: `binding`. Service: `services/binding/`. Catalog: §6 (AlphaGenome
> heads, ChromBPNet, FIMO + JASPAR), §1. Not actionable. Conventions: `specs/biology/README.md`.

## 1. Task

Predict transcription-factor binding, footprints, and accessibility for a sequence, and — if a
variant is supplied — the **occupancy/binding delta** it causes (gain/loss of sites).

## 2. Inputs

```python
class BindingRequest(BaseModel):
    subject: SequenceInput | GenomicInterval   # +organism
    organism: str
    assembly: str | None = None
    variant: Variant | None = None             # if present → compute deltas
    tfs: list[str] | None = None               # restrict to TF set; else panel/default
    motif_db: str = "JASPAR"                    # version pinned in provenance
```

## 3. Models/tools & selection

| Need | Tool | Catalog | Organism |
|---|---|---|---|
| Binding/accessibility prediction | **AlphaGenome heads** | §6/§1 | mammalian |
| Footprints / base-resolution | **ChromBPNet** | §6 | mammalian |
| Motif scan | **FIMO + JASPAR** | §6 | any |
| Non-mammalian priors | Evo 2-based | §1 | other clades |

## 4. Pipeline (transforms)

1. **(light) Prepare context** — extract sequence window; if variant present, build ref/alt sequences
   (allele substitution, strand handling).
2. **(heavy) Predict binding/accessibility** — AlphaGenome/ChromBPNet for mammalian; otherwise motif
   scan + Evo 2 priors.
3. **(light) Motif scan** — FIMO against JASPAR (pinned version) → motif hits with scores/positions.
4. **(light) Delta computation** — if variant: `delta = occupancy(alt) − occupancy(ref)` per TF;
   classify motif gain/loss.
5. **(light) Assemble** — motif logo + binding track (+ delta plot if variant).

## 5. Outputs

```python
class BindingResult(BaseModel):
    binding: list[BindingPred]               # {tf, score, position, strand}
    motif_hits: list[MotifHit]               # {motif, position, score}
    deltas: list[BindingDelta] | None        # {tf, value, direction} if variant
    confidence: Confidence
    provenance: Provenance                    # incl. motif_db version
```

- **Artifacts:** `motif_logo`, binding `genome_track`, delta plot.
- **Evidence:** salient binding/motif/delta claims with confidence + provenance.

## 6. Organism applicability

Mammalian binding heads are human/mouse only; other clades use motif scanning + Evo 2 priors. See
`supported_species.md`.

## 7. Failure modes & edge cases

- Variant ref mismatch → flag (as in variant effect).
- No motif hits → report explicitly.
- TF not in motif DB → note and skip.

## 8. Validation

ChIP-seq-anchored golden sites; motif-DB version pinning; variant-delta direction agreement;
coordinate correctness (`NFR-3`).

## 9. Related

`variant_effect_prediction.md` · `sequence_annotation.md` · `networks_systems_analysis.md`
(binding → GRN edges) · `capability-subgraphs/binding.md`.
