# Structure Prediction — Methodology & Programmatic Contract

> Capability: FR-18. Subgraph: `structure`. Service: `services/structure/`. Catalog: §3 (ESMFold),
> §4 (Boltz-2, nucleic-acid), §5 (DNAshapeR, Orca). Not actionable (design output → gated). Heavy/
> async. Conventions: `specs/biology/README.md`.

## 1. Task

Predict 3D structure (protein, nucleic-acid, complex), protein–ligand affinity, DNA shape, nucleosome
positioning, and chromatin contacts — with per-residue/per-position confidence.

## 2. Inputs

```python
class StructureRequest(BaseModel):
    kind: Literal["protein","nucleic_acid","complex","dna_shape","contacts"]
    sequences: list[SequenceInput] | None = None   # protein/NA chains
    interval: GenomicInterval | None = None        # for genomic structure (shape/contacts)
    ligand: LigandSpec | None = None               # SMILES/CCD for complex+affinity
    organism: str | None = None
    assembly: str | None = None                    # for genomic structure
```

## 3. Models/tools & selection

| Need | Model | Catalog |
|---|---|---|
| Fast single-sequence protein monomer | **ESMFold** | §3 |
| Complex / multimer / protein–ligand / NA-aware (+affinity) | **Boltz-2** | §4 |
| DNA shape (minor groove, roll, etc.) | **DNAshapeR** | §5 |
| Chromatin contacts | **Orca** | §5 |

Selection: monomer + speed → ESMFold; complex/ligand/NA or higher fidelity → Boltz-2; genomic
shape/contacts → DNAshapeR/Orca. Mostly organism-agnostic (sequence-based); genomic structure
respects assembly + circularity.

## 4. Pipeline (transforms)

1. **(light) Classify task** (monomer / complex / NA / shape / contacts) and validate inputs (alphabet,
   chain count, ligand spec).
2. **(light) Prepare inputs** — concatenate/format chains; build ligand representation (SMILES→model
   format) for complexes; for genomic structure, extract the interval sequence (assembly-framed).
3. **(heavy, async job) Predict** — run the selected model; for Boltz-2 complexes, also obtain
   predicted affinity.
4. **(light) Confidence extraction** — attach per-residue confidence (pLDDT-style); flag
   low-confidence regions/spans.
5. **(light) Assemble artifacts** — 3D structure (coords), contact map, or shape track.

## 5. Outputs

```python
class StructureResult(BaseModel):
    structure_ref: str | None                # storage_ref to coords (PDB/mmCIF)
    per_residue_confidence: list[float] | None
    affinity: float | None                   # Boltz-2 protein–ligand
    contacts_ref: str | None                 # contact map payload
    shape_track_ref: str | None
    low_confidence_regions: list[Span]
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** `structure_3d`, `contact_map`, shape `genome_track` (heavy payloads via
  `storage_ref`; `artifact_model.md`).
- **Evidence:** confidence summary, low-confidence flags, affinity (if any).

## 6. Actionable note

Pure prediction is analysis. **Design** (LigandMPNN/RFdiffusion) is generative → actionable/gated and
is specified in `protein_function_and_design.md` (FR-18a).

## 7. Failure modes & edge cases

- Sequence too long for ESMFold → route to a chunking strategy or Boltz-2, or warn.
- Invalid ligand spec → clarify/repair.
- Genomic structure without assembly → require/confirm.

## 8. Validation

Reference structures (e.g. held-out PDB) for RMSD/pLDDT sanity; affinity benchmarks for Boltz-2;
liveness for async jobs (`NFR-1`).

## 9. Related

`protein_function_and_design.md` · `metabolites_and_small_molecules.md` (docking/affinity) ·
`specs/services/structure_service.md` · `capability-subgraphs/structure.md`.
