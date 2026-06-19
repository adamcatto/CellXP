# Protein Function & Design — Methodology & Programmatic Contract

> Capability: FR-18a. Subgraph: `structure` (+ future `design`). Service: `services/structure/`,
> `services/reference/`. Catalog: §15 (eggNOG/InterProScan, CLEAN), §12 (LigandMPNN, RFdiffusion,
> ProteinMPNN), §3 (ESMFold). **Design output → actionable/gated.** Conventions:
> `specs/biology/README.md`.

## 1. Task

Two related modes: **(a) function annotation** of a protein (EC, domains, GO, orthology) and
**(b) design** of protein sequences/binders given a target or backbone.

## 2. Inputs

```python
class ProteinFunctionRequest(BaseModel):
    protein: SequenceInput                    # AA sequence (or ref → resolve)
    organism: str | None = None
    want: list[Literal["ec","domains","go","orthology","structure"]] = [...]

class ProteinDesignRequest(BaseModel):
    objective: Literal["sequence_for_backbone","binder_for_target","de_novo_scaffold"]
    backbone_ref: str | None = None           # structure storage_ref (for fixed-backbone design)
    target: SequenceInput | LigandSpec | None # binding target (protein/ligand)
    constraints: DesignConstraints = ...       # length, fixed residues, motifs
    num_designs: int = 8
```

## 3. Models/tools & selection

| Mode | Tool | Catalog |
|---|---|---|
| EC number prediction | **CLEAN** | §15 |
| Domains / families / GO | InterProScan / eggNOG | §15 |
| Structure (for context) | ESMFold / Boltz-2 | §3/§4 |
| Fixed-backbone sequence design | **LigandMPNN / ProteinMPNN** | §12 |
| De novo backbone / binder scaffold | **RFdiffusion** | §12 |

## 4. Pipeline (transforms)

**Function mode**
1. **(light)** validate AA alphabet; resolve reference if an ID was given.
2. **(heavy)** run function predictors (CLEAN for EC; InterProScan/eggNOG for domains/GO).
3. **(light, optional)** predict structure for context (`structure_prediction.md`).
4. **(light)** assemble function annotations + confidence.

**Design mode** (actionable)
1. **(light)** prepare target/backbone (structure ref → model input; ligand → representation).
2. **(heavy)** generate candidates — RFdiffusion (backbone) → LigandMPNN/ProteinMPNN (sequence);
   produce `num_designs`.
3. **(heavy)** score/filter — fold candidates (ESMFold/Boltz-2), check self-consistency
   (designed seq → predicted structure ≈ target backbone), predict binding/affinity where relevant.
4. **(light)** rank by objective; **gate:** mark `is_actionable` → human-review.

## 5. Outputs

```python
class ProteinFunctionResult(BaseModel):
    ec: list[str] | None
    domains: list[Domain] | None
    go_terms: list[str] | None
    orthologs: list[str] | None
    structure_ref: str | None
    confidence: Confidence
    provenance: Provenance

class ProteinDesignResult(BaseModel):
    designs: list[ProteinDesign]              # {sequence, predicted_structure_ref, scores}
    objective: str
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** function table; `structure_3d`; **design candidates** (actionable) with self-
  consistency + affinity scores.
- **Evidence:** function assignments / design scores with provenance.

## 6. Applicability

Sequence-based → largely organism-agnostic; function DBs vary in coverage. Design is generative →
always review-gated (`human_review_policy.md`).

## 7. Failure modes & edge cases

- Non-protein alphabet → reject.
- Design with no feasible candidate passing self-consistency → return with diagnostics, not as
  recommendation.

## 8. Validation

EC/domain accuracy vs curated sets; design self-consistency rate (scRMSD); **review-gate enforcement =
100%**.

## 9. Related

`structure_prediction.md` · `metabolites_and_small_molecules.md` (enzyme→reaction, docking) ·
`sequence_annotation.md` · `capability-subgraphs/structure.md`.
