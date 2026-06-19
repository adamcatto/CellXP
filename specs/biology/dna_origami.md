# DNA Origami — Methodology & Programmatic Contract

> Capability: FR-19. Subgraph: `origami` (**actionable → review-gated**). Service:
> `services/origami/`. Catalog: §16 (DAEDALUS/PERDIX/TALOS/ATHENA, cadnano/scadnano, oxDNA, CanDo).
> Conventions: `specs/biology/README.md`.

## 1. Task

Design a DNA-origami nanostructure: route a scaffold through a target shape, generate staple strands,
check constraints, and export a cadnano-compatible design (optionally simulate stability).

## 2. Inputs

```python
class OrigamiRequest(BaseModel):
    target_shape: ShapeSpec                   # wireframe/mesh or parametric shape + dimensions
    scaffold: SequenceInput | None = None     # scaffold sequence; default M13mp18 if omitted
    scaffold_length: int | None = None
    constraints: OrigamiConstraints = ...     # staple length bounds, crossover rules, etc.
    simulate: bool = False                    # run oxDNA/CanDo
```

## 3. Models/tools & selection

| Need | Tool | Catalog |
|---|---|---|
| Wireframe scaffold routing | **DAEDALUS / PERDIX / TALOS / ATHENA** | §16 |
| Layout / staple design + export | **cadnano / scadnano** | §16 |
| Stability simulation | **oxDNA** | §16 |
| Mechanical analysis | **CanDo** | §16 |

Tool by shape class: 2D polygon (PERDIX), 3D wireframe (DAEDALUS/TALOS), etc.

## 4. Pipeline (transforms)

1. **(light) Parse shape + constraints** — normalize the target geometry to a mesh/wireframe.
2. **(heavy) Scaffold routing** — compute a single scaffold path covering the wireframe (Eulerian-style
   routing); honor scaffold length.
3. **(heavy) Staple generation** — derive complementary staples; apply crossover/length rules; produce
   a cadnano/scadnano layout.
4. **(heavy, optional) Simulate** — oxDNA (stability) / CanDo (mechanics).
5. **(light) QC + export** — constraint/QC checks; export cadnano file + staple sequence list.
6. **gate:** mark output `is_actionable` → human-review gate.

## 5. Outputs

```python
class OrigamiResult(BaseModel):
    layout_ref: str                          # cadnano/scadnano export (storage_ref)
    staples: list[StapleStrand]              # {sequence, length, positions}
    design_params: dict[str, Any]
    qc: list[QcCheck]                        # constraint results
    simulation: dict[str, Any] | None        # stability/mechanics summary
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** `origami` layout (**actionable**) + cadnano export; simulation summary.
- **Evidence:** design parameters, QC/stability results.

## 6. Applicability

Synthetic constructs — organism-independent. Scaffold choice and staple chemistry are design
parameters, surfaced to the user.

## 7. Failure modes & edge cases

- Shape not routable with given scaffold length → report and suggest scaffold/shape adjustment.
- QC failures (unsatisfiable crossovers) → return with diagnostics, do not present as buildable.

## 8. Validation

Reproduce reference designs (known shapes) and compare staple sets; QC must pass before an export is
presented; **review-gate enforcement = 100%**.

## 9. Related

`structure_prediction.md` · `human_review_policy.md` · `specs/services/visualization_service.md` ·
`capability-subgraphs/origami.md`.
