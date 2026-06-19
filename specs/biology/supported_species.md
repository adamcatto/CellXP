# Supported Species — Reference & Programmatic Applicability

> Reference spec consumed by `entity_resolver`, `tool_use_policy.md` §4, and every methodology spec.
> Defines, **programmatically**, which organisms are first-class, their default assemblies, and which
> model families are applicable — so the agent never applies a mammalian-only oracle to a microbe.
> Conventions: `specs/biology/README.md`; coordinate rules: `coordinate_systems.md`.

## 1. Organism class drives model selection

The hard rule (a 100% guardrail, `success_metrics.md`): pick oracles by **organism class**, not by
default-to-human. Classes:

| Class | Examples | Genome traits the harness must respect |
|---|---|---|
| `mammalian` | human, mouse | linear chromosomes, large introns, distal regulation |
| `vertebrate_nonmammal` | zebrafish | linear; mammalian heads may not transfer |
| `invertebrate` | fly, worm | linear; model coverage varies |
| `plant` / `fungal` | *A. thaliana*, yeast | linear; specialized tools |
| `prokaryote` | *E. coli*, ***G. oxydans*** | often **circular**, single-replicon, gene-dense, intron-poor, operon-organized |

## 2. Applicability matrix (model family × organism class)

| Capability / model | mammalian | prokaryote | other eukaryote |
|---|---|---|---|
| AlphaGenome (regulatory/variant/binding) | ✅ | ❌ | ⚠️ limited |
| Evo 2 (sequence scoring/annotation priors) | ✅ | ✅ | ✅ |
| SpliceAI (splicing) | ✅ | ❌ (no spliceosomal introns) | ⚠️ |
| ESMFold / Boltz-2 (structure) | ✅ | ✅ | ✅ (sequence-based) |
| Bakta/Pyrodigal (annotation) | ❌ | ✅ | ❌ |
| Helixer (annotation) | ✅ | ❌ | ✅ |
| GWAS/QTL resources | ✅ (human) | ❌ | ⚠️ sparse |
| CRISPR design | ✅ | ✅ (Cas/PAM/codon organism-specific) | ✅ |
| Metabolic models (CarveMe/ModelSEED) | ⚠️ | ✅ (strong for microbes) | ⚠️ |

✅ applicable · ⚠️ partial / use with care · ❌ not applicable (selection rule MUST exclude).

## 3. Programmatic contract

```python
class SpeciesProfile(BaseModel):
    organism: str                            # canonical name / taxid
    organism_class: str                      # one of §1
    default_assembly: str                    # e.g. GRCh38, GRCm39, ASM ... for G. oxydans
    topology: Literal["linear","circular","mixed"]
    applicable_models: list[str]             # model keys valid for this organism
```

- `entity_resolver` MUST resolve organism → `SpeciesProfile` (with assembly) before coordinate ops
  (`FR-11`); when the work is strain-specific, it MUST resolve to a `StrainProfile` (§5.4) and use the
  **strain's** assembly/replicons, not the species default.
- `tool_use_policy` MUST filter candidate models by `applicable_models` (exclude ❌; warn on ⚠️).
  Strains inherit the parent species' applicability unless overridden.
- First-class v1 organisms: **human (GRCh38)**, **mouse (GRCm39)**, and **bacteria** (e.g.
  *G. oxydans*, strain 621H) with their RefSeq assemblies. Others are best-effort. Adding species §5.1;
  adding strains §5.4.

## 4. Failure modes

- Unknown organism → clarify or refuse the coordinate-dependent capability.
- Organism with no applicable oracle for the requested capability → explicit "unsupported organism for
  this capability" (not a wrong-model result).

## 5. Adding a new species (extension procedure)

Adding an organism is a **data + applicability** change, not a code change to capabilities — that is
the point of the `SpeciesProfile` contract (§3). To onboard a species:

### 5.1 What a new species MUST provide

1. **Identity & taxonomy** — canonical name + NCBI taxid, and its `organism_class` (§1); if it doesn't
   fit an existing class, add a class here first (and decide model applicability for it).
2. **Reference assembly** — a `default_assembly` (RefSeq/Ensembl accession), its **topology**
   (linear/circular/mixed), replicon list, and the coordinate convention — registered with the
   reference service (`services/reference/`, `specs/services/reference_genome_service.md`).
3. **Applicability decisions** — for each capability/model, mark ✅/⚠️/❌ in the matrix (§2) and set
   `applicable_models`. A model is ✅ only if it is **validated** (or vendor-documented) for that
   organism class; default to ⚠️/❌ rather than optimistic ✅.
4. **Annotation source** — gene models/annotation tooling appropriate to the class (e.g.
   Bakta/Pyrodigal for bacteria, Helixer for eukaryotes) and, where available, a reference annotation.
5. **Coordinate test fixtures** — at least one round-trip + edge-case fixture (incl. origin-wrap for
   circular genomes) so `NFR-3` coverage extends to the new organism.

### 5.2 Roughly how to do it

1. Add/confirm the `organism_class` and its applicability row (§1–§2).
2. Register the assembly (accession, topology, replicons) in the reference service.
3. Add a `SpeciesProfile` entry (the registry record; storage TBD — see note) and `applicable_models`.
4. Add coordinate fixtures + an annotation smoke test; run the organism through one golden query per
   applicable capability.
5. Update the matrix + first-class list and changelog.

### 5.3 Acceptance for a new species

- Resolvable by `entity_resolver` to a `SpeciesProfile` with a valid assembly (`FR-11`).
- `tool_use_policy` selects only applicable models for it (no ❌ ever selected — the 100% guardrail).
- Coordinate fixtures pass (`NFR-3`); one golden query per applicable capability passes.

### 5.4 Adding a new strain (vs a new species)

A **strain** is a sub-species lineage (e.g. *G. oxydans* **621H**, *E. coli* **K-12 MG1655**). It is
**not** a new species: it inherits the parent species' taxonomy, `organism_class`, topology
conventions, and model applicability — what differs is the **specific genome** (assembly accession,
plasmids/replicons, accessory-gene content) and, for engineered strains, a lineage of applied edits.
This distinction matters most for **microbes**, where strain-level genome differences are large and
drive strain-engineering work (`specs/agent/session_types.md` — *strain optimization*;
`networks_systems_analysis.md` — strain-specific GEMs).

A strain refines a `SpeciesProfile`:

```python
class StrainProfile(BaseModel):
    strain_id: str                           # e.g. "g_oxydans_621H"
    species: str                             # parent organism / taxid → inherits class + applicability
    assembly: str                            # strain-specific genome accession (its own, not the species default)
    replicons: list[str]                     # chromosome(s) + plasmids, each with topology
    accessory_notes: str | None = None       # notable gene-content / plasmid differences vs reference strain
    derived_from: str | None = None          # parent strain_id, if engineered
    modifications: list[EditSpec] = []        # applied edits (provenance) for engineered strains
    is_reference: bool = False                # the default/reference strain for the species
```

**What a new strain MUST provide**
1. **Parent species** — an existing `SpeciesProfile` (add the species first if absent, §5.1).
2. **Strain genome** — its own assembly accession + **replicon list with per-replicon topology**
   (bacteria often carry circular plasmids alongside a circular chromosome) registered with the
   reference service.
3. **Accessory differences** — note plasmids / accessory genes that differ from the species reference
   (affects annotation, CRISPR targeting, and GEMs).
4. **Lineage (engineered strains)** — `derived_from` + the `modifications` (edits) that produced it,
   with provenance (`state_schema.md` §8). An engineered strain proposed by the agent (e.g. from an
   inverse-design or genome-editing run) MAY be registered **workspace-scoped** in a session before
   any global promotion (`session_types.md`).
5. **Fixtures** — strain-specific coordinate fixtures (per replicon, incl. plasmids).

**Roughly how to do it**
1. Ensure the parent `SpeciesProfile` exists; create a `StrainProfile` referencing it.
2. Register the strain assembly + replicons (topologies) in the reference service; set the reference
   strain if this is the default.
3. Inherit `applicable_models` from the species (override only if a model is strain-sensitive); attach
   accessory notes.
4. For engineered strains, record `derived_from` + `modifications`; keep them session-scoped until
   validated.
5. Add per-replicon coordinate fixtures + an annotation smoke test; run a golden query.

**Acceptance:** resolvable to a `StrainProfile` whose **strain-specific** assembly/replicons are used
for all coordinate-dependent work (not the species default); plasmids handled with correct topology;
engineered-strain lineage is provenance-complete.

> **TODO (revisit during implementation).** This is a design-time contract. The concrete mechanics —
> where the species/**strain**/assembly **registry** lives (config file vs DB table vs `specs/data/*`),
> how applicability is encoded (declarative table vs per-model capability flags), how engineered/
> workspace-scoped strains are stored and promoted, and the exact onboarding CLI/workflow — are **not
> yet decided** and should be finalized once the reference service and data model are implemented.
> Until then, treat §5 as the requirements, not the final procedure.

## 6. Related

`tool_use_policy.md` · `coordinate_systems.md` · `supported_assays.md` ·
`specs/services/reference_genome_service.md` · all methodology specs ·
`documentation/reference/external_models_and_services.md` · `CONTRIBUTING.md` (community contribution
guide for species/strains/assays/etc.).
