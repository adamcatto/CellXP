# CRISPR Design — Methodology & Programmatic Contract

> Capability: FR-15. Subgraph: `crispr` (**actionable → review-gated**, FR-25/26). Service:
> `services/crispr/`. Catalog: §10 (Rule Set 2/Azimuth, BE-Hive, PRIDICT, Cas-OFFinder, CFD).
> Conventions: `specs/biology/README.md`.

## 1. Task

Design genome-editing reagents for a target — gRNAs for knockout/knock-in, and base/prime edits —
with on-target efficiency and off-target specificity scoring, plus editing-system trade-offs.

## 2. Inputs

```python
class CrisprRequest(BaseModel):
    target: GeneRef | GenomicInterval        # +organism+assembly
    organism: str
    assembly: str
    edit_type: Literal["knockout","knockin","base_edit","prime_edit","interference"]
    edit_spec: EditSpec | None = None        # for base/prime: desired ref→alt at position
    cas: str | None = None                   # e.g. SpCas9, SaCas9, Cas12a; default per organism
    pam: str | None = None                   # override PAM; default from cas
    num_guides: int = 10
```

Preconditions: organism+assembly resolved; target sequence retrievable; Cas/PAM compatible with
organism (`supported_species.md`).

## 3. Models/tools & selection

| Need | Tool | Catalog |
|---|---|---|
| On-target efficiency | **Rule Set 2 / Azimuth** | §10 |
| Base-edit outcome | **BE-Hive** | §10 |
| Prime-edit outcome | **PRIDICT** | §10 |
| Off-target enumeration | **Cas-OFFinder** | §10 |
| Off-target specificity score | **CFD** | §10 |

## 4. Pipeline (transforms)

1. **(light) Resolve target → sequence + coordinates**; determine strand; for knock-in/base/prime,
   locate the exact edit position.
2. **(light) PAM site enumeration** — scan both strands for the Cas's PAM within the target window;
   extract candidate protospacers (organism/Cas-aware; respect circular coordinates).
3. **(heavy) On-target scoring** — score each candidate (Rule Set 2); for base/prime, predict edit
   outcome/efficiency window (BE-Hive/PRIDICT).
   Rule Set 2 consumes the real 30-bp genomic context (4 upstream + spacer + PAM + 3 downstream),
   extracted from the named assembly and strand; fabricated or missing flanks invalidate the score.
4. **(heavy) Off-target analysis** — enumerate genome-wide near-matches (Cas-OFFinder) within a
   mismatch budget; score specificity (CFD); aggregate an off-target profile per guide.
   Production execution binds results to an attested tool revision and organism/assembly index;
   sequence-QC fixtures are not biological scores and cannot satisfy this step.
5. **(light) Rank + assemble** — multi-objective rank (on-target↑, off-target↓, position fit);
   build a sortable guide table with PAM/strand/score context.
6. **gate:** mark output `is_actionable` → human-review gate.

## 5. Outputs

```python
class CrisprResult(BaseModel):
    guides: list[Guide]                      # ranked
    editing_system: str                      # chosen Cas/modality + rationale

class Guide(BaseModel):
    spacer: str
    pam: str
    strand: str
    cut_site: int                            # assembly coordinate
    on_target_score: float
    off_targets: list[OffTarget]             # {locus, mismatches, cfd}
    specificity_score: float
    feasibility_notes: list[str]
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** `guide_table` (**actionable**); sequence-context view.
- **Evidence:** per-guide scores + off-target profile + editing-system rationale.

## 6. Organism applicability

PAM availability, Cas compatibility, codon/editing-window context are organism-specific (e.g.
*G. oxydans*). Off-target search uses the **organism's** genome, circular-aware.

## 7. Failure modes & edge cases

- No PAM in window → report and suggest alternate Cas/PAM.
- Repetitive/low-complexity target → flag high off-target risk.
- Missing edit_spec for base/prime → clarify (`FR-7`).

## 8. Validation

Known-efficacy guides as golden seeds; off-target recall vs published sets; **review-gate enforcement
= 100%** (`success_metrics.md` D5); coordinate correctness (`NFR-3`).

## 9. Related

`inverse_edit_design.md` (consumes this for realizability) · `human_review_policy.md` ·
`specs/services/crispr_service.md` · `capability-subgraphs/crispr.md`.
