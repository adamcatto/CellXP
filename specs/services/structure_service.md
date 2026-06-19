# Structure Service

> Status: Draft v0.1. Logical service contract for protein, nucleic-acid, complex, ligand-aware, DNA
> shape, and contact-map prediction. Impl: `src/backend/cellxp/services/structure/`.
> Methodology: `specs/biology/structure_prediction.md`,
> `specs/biology/protein_function_and_design.md`,
> `specs/biology/metabolites_and_small_molecules.md`. Catalog:
> `documentation/reference/external_models_and_services.md` §3, §4, §5, §12, §13, §15.

## 1. Purpose

Provide stable access to structure and molecular modeling tools: ESMFold/Boltz-2-class prediction,
RNA/DNA secondary or 3D structure tools, DNA shape/contact predictors, protein function helpers, and
protein/sequence design tools. Prediction outputs are analysis; generative design outputs are
actionable and review-gated.

## 2. Operations

```python
class StructureService(Service):
    def predict_structure(self, request: StructureRequest) -> ServiceResult[StructureResult]: ...
    def predict_contacts(self, request: ContactMapRequest) -> ServiceResult[ContactMapResult]: ...
    def predict_dna_shape(self, request: DnaShapeRequest) -> ServiceResult[DnaShapeResult]: ...
    def annotate_protein_function(self, request: ProteinFunctionRequest) -> ServiceResult[ProteinFunctionResult]: ...
    def design_protein(self, request: ProteinDesignRequest) -> ServiceResult[ProteinDesignResult]: ...
    def score_ligand_binding(self, request: MoleculeRequest) -> ServiceResult[MoleculeResult]: ...
```

## 3. Inputs

Inputs may be protein sequences, RNA/DNA sequences, multi-chain complex specs, ligands
(SMILES/InChI/CCD), structure object refs, or genomic intervals for DNA shape/contact tasks. The
service validates alphabets, chain identity, ligand parseability, assembly context, and sequence
length limits before dispatch.

## 4. Execution

Most structure operations are heavy and SHOULD run as async jobs. The service emits liveness updates
for queued/running GPU jobs and returns partial metadata as soon as it can create an artifact
placeholder.

Light operations include input normalization, format conversion, confidence extraction, feature
summarization, and artifact packaging. Heavy operations include Boltz-2/ESMFold inference,
RFdiffusion/LigandMPNN generation, docking/affinity prediction, Orca contact prediction, and large
protein-function scans.

## 5. Outputs & Artifacts

| Output | Artifact type | Actionable | Storage |
|---|---|---:|---|
| predicted structure | `structure_3d` | no | mmCIF/PDB in object storage |
| per-residue confidence | `structure_confidence_track` | no | inline summary + object |
| contact map | `contact_map` | no | object storage |
| DNA shape | `genome_track` | no | object storage |
| ligand pose/affinity | `structure_3d`, `affinity_panel` | no | object storage |
| protein function | `function_table` | no | inline preview + object |
| protein/binder design | `protein_design_table`, `structure_3d` | yes | object storage |

## 6. Provenance & Confidence

Provenance records model/tool, weights/revision, input sequences and structure refs, ligand
standardization, chain mapping, template/MSA settings where applicable, random seed for generative
design, and output content hashes. Confidence uses native metrics where available: pLDDT-like scores,
PAE/contact confidence, affinity confidence, domain/EC hit quality, and self-consistency for designs.

## 7. Safety & Review

`design_protein` outputs are actionable/generative and MUST create review items. Pure prediction,
annotation, or affinity analysis is not gated unless risk policy escalates it.

## 8. Failure Modes

- sequence too long: route to supported strategy or return validation error with limits;
- invalid alphabet/ligand: validation error;
- low-confidence structure: valid result with confidence flags, not failure;
- no feasible design: return diagnostics and do not create recommendation;
- GPU/model failure: recoverable `RunError` if other subtasks can continue.

## 9. Requirements

- **STS-1** Heavy model calls MUST use async job semantics when they exceed synchronous latency
  budgets.
- **STS-2** Structure coordinate files and contact maps MUST be stored as immutable object payloads.
- **STS-3** Per-residue/per-position confidence MUST be exposed wherever the selected model provides
  it.
- **STS-4** Generative protein design outputs MUST be actionable and review-gated.
- **STS-5** Ligand and chain normalization MUST be recorded in provenance.

## 10. Related

`specs/biology/structure_prediction.md` · `specs/biology/protein_function_and_design.md` ·
`specs/biology/metabolites_and_small_molecules.md` · `specs/interface/artifact_model.md`.
