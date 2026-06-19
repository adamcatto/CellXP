# Model-Guided Inverse Edit Design — Methodology & Programmatic Contract

> Capability: FR-18c (**flagship composed**, actionable → review-gated). Subgraph: composed loop over
> `variant_effect` + `crispr` (+ `binding`/`structure`). Catalog: §11 (inverse design), §1 (forward
> oracles), §10 (editors/off-target). Conventions: `specs/biology/README.md`. Cookbook:
> `task_patterns.md` §6.

## 1. Task

The **inverse** of variant effect prediction: given a *desired functional effect*, search the
realizable edit space for edit strategies that achieve it while **maximizing on-target effect and
minimizing off-target/collateral impact**.

## 2. Inputs

```python
class InverseDesignRequest(BaseModel):
    target_effect: EffectTarget               # the goal, expressed on a forward-model readout
    locus: GenomicInterval | GeneRef          # editable region
    organism: str
    assembly: str
    editor: str | None = None                 # Cas/base/prime; default per organism
    objective_weights: ObjectiveWeights = ... # on-target↑, off-target↓, collateral↓, feasibility↑
    budget: SearchBudget = ...                # max candidates/iterations (control-flow budget)

class EffectTarget(BaseModel):
    readout: str                              # assay/head (supported_assays.md) e.g. "expression:GeneX:tissueY"
    direction: Literal["increase","decrease","abolish","create","shift"]
    magnitude: float | None = None
```

## 3. Components (composed)

| Role | Tool | Spec / catalog |
|---|---|---|
| Objective oracle (forward effect) | AlphaGenome / Evo 2 (+ binding) | `variant_effect_prediction.md`, §1 |
| Realizability (can we make the edit?) | CRISPR/base/prime design | `crispr_design.md`, §10 |
| Off-target penalty | Cas-OFFinder + CFD | §10 |
| Collateral penalty | nearby-readout deltas (forward oracle) | `variant_effect_prediction.md` |
| Optimizer | greedy / evolutionary / gradient-guided | §11 |

## 4. Pipeline (the loop / transforms)

1. **(light) Frame objective** — turn `target_effect` into a scalar objective on the forward oracle's
   readout; define the editable window.
2. **(light) Propose** — generate candidate edits within the window (point/indel/regulatory edits the
   editor can realize).
3. **(heavy) Score on-target** — run the forward oracle on each candidate → predicted effect vs target.
4. **(heavy) Score penalties** — off-target (Cas-OFFinder+CFD), collateral (deltas on neighboring
   readouts), feasibility (editor/PAM/window/efficiency from `crispr_design.md`).
5. **(light) Aggregate + select** — multi-objective score (`objective_weights`); keep Pareto-best.
6. **(loop)** repeat propose→score→select until convergence or `budget`
   (`control-flow/replanning_and_budget.md`); each iteration's intermediates remain inspectable.
7. **gate:** mark output `is_actionable` → human-review.

## 5. Outputs

```python
class InverseDesignResult(BaseModel):
    candidates: list[EditCandidate]          # ranked, Pareto front flagged

class EditCandidate(BaseModel):
    edit: EditSpec                           # what to change (ref→alt @ pos) + editor/guide
    predicted_effect: AssayDelta             # on-target vs target
    off_target_profile: list[OffTarget]
    collateral: list[AssayDelta]             # unintended nearby effects
    feasibility: dict[str, Any]              # editor/PAM/efficiency
    score: float
    confidence: Confidence                    # compounded (oracle + editor)
    provenance: Provenance
```

- **Artifacts:** ranked candidate-edit table (**actionable**), effect/off-target/collateral views.
- **Evidence:** per-candidate predicted effect + penalties with compounded confidence and full
  provenance of every oracle/editor call.

## 6. Applicability

Organism-appropriate forward oracle is mandatory (mammalian AlphaGenome vs microbial Evo 2;
`supported_species.md`). Editor/PAM organism-specific. Always review-gated.

## 7. Failure modes & edge cases

- No realizable edit achieves the target within budget → report best partial + the gap, not a
  fabricated success.
- Strong on-target but unacceptable off-target/collateral → surfaced explicitly; not auto-recommended.
- Convergence stalls → stop at budget, return Pareto set (`replanning_and_budget.md`).

## 8. Validation

Round-trip checks (designed edit → forward oracle reproduces intended effect); off-target recall;
**review-gate enforcement = 100%**; compounded-confidence honesty.

## 9. Related

`variant_effect_prediction.md` · `crispr_design.md` · `binding_site_prediction.md` ·
`networks_systems_analysis.md` · `task_patterns.md` §6 · `human_review_policy.md` ·
`documentation/explanation/architecture_overview.md` §5.1.
