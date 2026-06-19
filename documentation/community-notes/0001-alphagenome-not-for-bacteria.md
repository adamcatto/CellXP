# 0001 — AlphaGenome heads don't apply to bacteria — use Evo 2

- **Status:** active
- **Scope:** AlphaGenome (and other mammalian regulatory heads, e.g. SpliceAI) × `prokaryote`
  organism class (e.g. *E. coli*, *G. oxydans*); all current versions.
- **Contributor:** core team · **Date:** 2026-06-16
- **Owning spec(s):** `specs/biology/supported_species.md` §2 (applicability matrix),
  `specs/agent/tool_use_policy.md` §4, `specs/biology/variant_effect_prediction.md`.

## Claim

AlphaGenome's regulatory/variant/binding heads are trained on **mammalian** (human/mouse) genomes and
their regulatory grammar. Applying them to **bacterial** sequences is invalid and will produce
confident-but-meaningless output. Use **Evo 2** (cross-species, microbial-capable) for prokaryotic
variant scoring/annotation priors instead.

## Evidence / source

- Bacterial genomes violate the assumptions baked into mammalian models: typically **circular**,
  single-replicon, gene-dense, **intron-poor** (no spliceosomal splicing → SpliceAI N/A),
  operon-organized, with distinct promoter/regulatory grammar.
- AlphaGenome's training corpus and assay heads (tissue/cell-type RNA/ATAC/ChIP/splicing) have no
  bacterial analogue.

## Scope & limits

- Applies to the whole `prokaryote` class. Does **not** restrict Evo 2, ESMFold, Boltz-2, or
  conventional annotation tools (Bakta/Pyrodigal), which remain valid for bacteria.
- Mammalian and (with care) some other eukaryotic uses of AlphaGenome are unaffected.

## Suggested action

- Already encoded as a **hard rule**: `tool_use_policy` MUST exclude AlphaGenome for `prokaryote`
  organisms, and the species applicability matrix marks it ❌ (`supported_species.md` §2). This is a
  100% guardrail (`specs/product/success_metrics.md`).
- For prokaryotic variant effect, route to **Evo 2**; for regulatory features, use prokaryotic
  annotation tools + motif scanning rather than mammalian heads.

## Notes

This note is **resolved-in-contract** (the rule is enforced), but kept `active` as the canonical
explanation of *why* — useful when onboarding a new prokaryotic species/strain (`supported_species.md`
§5.1/§5.4).
