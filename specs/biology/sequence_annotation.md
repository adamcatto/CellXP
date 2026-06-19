# Sequence Annotation — Methodology & Programmatic Contract

> Capability: FR-16. Subgraph: `annotation`. Service: `services/reference/`. Catalog: §7
> (Pyrodigal/Bakta, Helixer, tRNAscan-SE/Infernal, antiSMASH; AlphaGenome regulatory), §15
> (eggNOG/InterProScan, CLEAN). Not actionable. Conventions: `specs/biology/README.md`.

## 1. Task

Annotate a sequence/interval/genome with structural features (genes, ORFs, ncRNA), regulatory
elements, motifs, and functional assignments (EC/GO/domains) — eukaryotic and **prokaryotic**.

## 2. Inputs

```python
class AnnotationRequest(BaseModel):
    subject: SequenceInput | GenomicInterval | GenomeRef    # +organism
    organism: str
    assembly: str | None = None
    scope: Literal["interval","whole_genome"] = "interval"
    methods: list[str] | None = None         # user method preference (FR-16); else auto
    want_function: bool = True               # EC/GO/domain assignment
    want_regulatory: bool = False            # mammalian regulatory elements
```

Preconditions: organism class known (prokaryote vs eukaryote) — drives tool choice.

## 3. Models/tools & selection

| Need | Tool | Catalog | Organism |
|---|---|---|---|
| Bacterial gene finding/annotation | **Pyrodigal / Bakta** | §7 | prokaryote |
| Eukaryotic gene models | **Helixer** | §7 | eukaryote |
| Regulatory elements | **AlphaGenome / DeepRegFinder** | §7 | mammalian |
| ncRNA | tRNAscan-SE / Infernal | §7 | any |
| BGCs (secondary metabolism) | **antiSMASH** | §7 | microbial |
| Functional/EC assignment | eggNOG / InterProScan / **CLEAN** | §15 | any |

## 4. Pipeline (transforms)

1. **(light) Classify scope + organism class**; pick tool set (may ask method preference, `FR-7`).
2. **(heavy) Structural annotation** — run gene finder (Pyrodigal/Bakta or Helixer); for circular
   bacterial genomes, handle origin wrap and operon structure.
3. **(light/heavy) ncRNA + BGC scans** — tRNAscan-SE/Infernal; antiSMASH for clusters.
4. **(heavy) Functional assignment** — map predicted proteins to EC/GO/domains (eggNOG/InterProScan;
   CLEAN for enzyme EC).
5. **(light, optional) Regulatory** — mammalian regulatory elements via AlphaGenome heads.
6. **(light) Assemble** — merge features into a coordinate-anchored feature set + annotation track.

## 5. Outputs

```python
class AnnotationResult(BaseModel):
    features: list[Feature]                  # {type, start, end, strand, name, attributes}
    functions: list[FunctionAssignment]      # {feature_id, ec?, go?, domains?, source}
    summary: dict[str, Any]                  # counts, notable features
    confidence: Confidence
    provenance: Provenance
```

- **Artifacts:** `genome_track` (annotation); feature table. Exportable as GFF/BED
  (`artifact_model.md`).
- **Evidence:** notable features/functions with tool provenance.

## 6. Organism applicability

Prokaryotic tools are first-class (circular/operon-aware). Mammalian regulatory annotation only via
mammalian models. See `supported_species.md`.

## 7. Failure modes & edge cases

- Wrong organism-class tool (e.g. eukaryotic finder on bacteria) → prevented by selection rule.
- Low-quality/short input → partial annotation + warning.
- Ambiguous coordinates / no assembly for whole-genome → require/confirm.

## 8. Validation

Benchmark genomes with reference annotations (feature-level precision/recall); EC-assignment accuracy;
coordinate correctness (`NFR-3`).

## 9. Related

`binding_site_prediction.md` · `protein_function_and_design.md` (function detail) ·
`networks_systems_analysis.md` (annotation → GEM) · `capability-subgraphs/annotation.md`.
