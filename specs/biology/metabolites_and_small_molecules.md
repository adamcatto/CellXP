# Metabolites & Small Molecules — Methodology & Programmatic Contract

> Capability: FR-18b. Subgraph: `structure`/`binding` (+ systems). Service: `services/structure/`,
> `services/binding/`. Catalog: §13 (RDKit, docking, affinity), §14 (metabolic models). Conventions:
> `specs/biology/README.md`.

## 1. Task

Cheminformatics on small molecules/metabolites (parsing, descriptors, similarity), protein–ligand
binding/affinity prediction, and the molecule side of genome-scale metabolic modeling (substrates,
products, pathways) — for metabolic-engineering use-cases.

## 2. Inputs

```python
class MoleculeRequest(BaseModel):
    molecules: list[LigandSpec]               # SMILES / InChI / name → resolved
    op: Literal["descriptors","similarity","standardize","docking","affinity"]
    target: SequenceInput | str | None = None # protein target (seq or structure ref) for docking/affinity
    reference: LigandSpec | None = None        # for similarity
    organism: str | None = None                # context for metabolic relevance
```

## 3. Models/tools & selection

| Need | Tool | Catalog |
|---|---|---|
| Parse / standardize / descriptors / fingerprints | **RDKit** | §13 |
| Similarity search | RDKit fingerprints + index | §13 |
| Protein–ligand docking | docking engine (e.g. DiffDock/AutoDock-class) | §13 |
| Binding affinity | **Boltz-2** (protein–ligand) | §13/§4 |
| Pathway/flux context | GEM tools (`networks_systems_analysis.md`) | §14 |

## 4. Pipeline (transforms)

1. **(light) Parse + standardize** — SMILES/InChI → canonical molecule; sanitize; resolve names to
   structures.
2. **(light) Descriptors/fingerprints** — compute properties (MW, logP, TPSA…) and fingerprints.
3. **(light) Similarity** — Tanimoto vs reference / library.
4. **(heavy) Docking/affinity** — dock against the protein target (prepare receptor from seq/structure
   ref) and/or predict affinity (Boltz-2 complex).
5. **(light) Assemble** — molecule cards, similarity table, pose/affinity artifacts.

## 5. Outputs

```python
class MoleculeResult(BaseModel):
    molecules: list[MoleculeRecord]          # canonical, descriptors, fingerprint id
    similarity: list[SimilarityHit] | None
    docking: list[DockingPose] | None        # {pose_ref, score}
    affinity: float | None
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** molecule/descriptor table, similarity table, docking pose (`structure_3d`-like),
  affinity readout.
- **Evidence:** descriptors/affinity/similarity claims with provenance.

## 6. Applicability

Cheminformatics is organism-independent; metabolic relevance is organism-specific (links to GEMs,
`networks_systems_analysis.md`). Metabolites are first-class entities (`mission.md` §4).

## 7. Failure modes & edge cases

- Unparseable/invalid SMILES → reject with reason.
- Docking without a usable receptor → require target structure (predict first).

## 8. Validation

Descriptor correctness vs RDKit reference; affinity/docking benchmarks; provenance completeness.

## 9. Related

`protein_function_and_design.md` (enzyme function) · `structure_prediction.md` (affinity) ·
`networks_systems_analysis.md` (flux/yield) · `capability-subgraphs/structure.md`.
