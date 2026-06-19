# annotation Subgraph

> Status: Draft v0.1. Capability: sequence/genome annotation (`FR-16`). Parent: `graph_spec.md` §5.
> Impl: `agent/subgraphs/annotation.py`, `services/reference/`. Methodology:
> `specs/biology/sequence_annotation.md`. Not actionable.

## Purpose

Annotate sequences/intervals/genomes with gene models, regulatory features, motifs, ORFs, and
functional assignments — eukaryotic and **prokaryotic**.

## Input (Subtask)

A sequence/interval/genome (+ organism), optional annotation-method preference.

## Steps

1. **(light)** detect input scope (interval vs whole genome) + organism class.
2. **(heavy)** gene finding/annotation: **Pyrodigal/Bakta** (bacterial), **Helixer** (eukaryotic);
   regulatory elements via **AlphaGenome/DeepRegFinder** (mammalian); ncRNA via tRNAscan-SE/Infernal
   (catalog §7). May ask the user for method preference (`FR-16`).
3. **(light/heavy)** functional/EC assignment: eggNOG/InterProScan + **CLEAN** (catalog §15) for
   enzymes; BGCs via **antiSMASH**.
4. **(light)** emit an annotation track + feature summary.

## Outputs

- **evidence:** features (genes/ORFs/regulatory/ncRNA), functional/EC assignments, citations.
- **artifacts:** `genome_track` (annotation), feature table.

## Organism notes

Prokaryotic tools are first-class; circular/operon-aware. Mammalian regulatory annotation only via
mammalian models.

## Open questions

- Default annotation pipeline per organism class.
- Whether to always offer a method-preference clarification.

## Related

`specs/biology/sequence_annotation.md` · catalog §7/§15 · `binding.md` · `task_patterns.md` §4.
