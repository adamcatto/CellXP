# Future Additions

> Status: Draft v0.1 — **living backlog** for things **not yet on the near-term roadmap**: scope
> deferred from v1, exploratory directions, and a future-capabilities backlog. This is distinct from
> `roadmap.md` (near-term, committed plan). Entries here are *not commitments*. Keep entries short;
> deepen one only when it's picked up. Referenced by `mission.md` and `product_requirements.md` §3.

**Promotion gate (when something leaves this file for `roadmap.md`):** an item graduates only when it
is (a) **prioritized**, (b) **scoped** enough to estimate, and (c) its **prerequisites are known**.
Promotion = move the entry into `roadmap.md` (Now/Next/Later), then write the `FR-*` and the
relevant `specs/biology/` + capability/subgraph specs.

**Status vocabulary (shared with `roadmap.md`):**
`idea → exploring → committed → in-progress → shipped` (or `deferred`). Everything in this file is
`idea`, `exploring`, or `deferred` by definition.

## 1. Deferred from v1 (out of current scope)

From `product_requirements.md` §3 — tracked, not abandoned:

- Multi-user **real-time collaboration**.
- **In-product training/fine-tuning** of models (note: *offline* reasoning-LLM post-training is a
  separate track, §3).
- **Mobile-native** apps.
- **Clinical / regulated** use (CR-5 — research-grade only).
- **Wet-lab execution / hardware control** (we design & recommend; possible future lab/LIMS
  integration).

## 2. Exploratory entities (extend the same machinery)

From `mission.md` §4 — acknowledged extensions, gated until prioritized:

- **Glycans** (glycomics), **lipids** (lipidomics), **cells / cell types** (single-cell;
  catalog §18 is already exploratory).

## 3. Reasoning-LLM post-training track

Offline SFT/DPO/**RLVR** of the agent's reasoning model — owned by
`specs/training/post_training.md` + `documentation/explanation/post_training.md`. Distinct from the
"no in-product training" v1 boundary (§1); the domain foundation models are never fine-tuned
in-product.

## 4. Future capabilities (design backlog)

Each entry: what it is · inputs/outputs · components it composes · prerequisites · risks/ethics ·
status. Pick one up by promoting it to `roadmap.md`, then FRs + a capability/biology spec + (often) a
session type/macro.

### FC-1 — Personal genome annotation & interpretation *(flagship)*

- **What:** end-to-end annotation/interpretation of an **individual genome** — from a **VCF/BCF**
  (variant calls against a reference) or a **FASTA** (assembled genome) — into an integrated,
  research-grade report spanning **predicted molecular effects, disease-risk signals, pharmacogenomics
  (PGx), ancestry, and carrier/notable-variant findings**.
- **Inputs:** VCF/BCF + reference assembly (organism/assembly explicit, `coordinate_systems.md`), or
  FASTA (de novo/assembled) → call/normalize variants first; optional sample metadata (with consent).
- **Outputs:** per-variant molecular effects, known-variant annotation, trait/disease **polygenic risk
  scores (research-grade)**, PGx annotations, **ancestry** inference, carrier status, and a synthesized,
  cited, confidence-qualified report + interactive artifacts; full provenance.
- **Composes (mostly existing pieces):** variant effect (FR-13, AlphaGenome/Evo 2), variant annotation
  DBs (ClinVar/dbSNP/gnomAD frequencies; catalog §8), GWAS/PRS (FR-14, §9), ancestry reference panels,
  PGx knowledge (e.g. PharmGKB/CPIC), networks/pathways (FR-18d) and RAG (FR-20) for interpretation.
  Naturally a **macro** + a **"Personal genome" session type** (`session_types.md`,
  `routing_policy.md`).
- **Prerequisites:** scalable **batch variant processing** (thousands–millions of variants — not the
  single-variant path), robust VCF/BCF parsing + joint reference handling, PRS model integration,
  ancestry panels, and **strong privacy controls** (local-first, NFR-7) for highly sensitive data.
- **Risks / ethics (important):** this **borders on clinical** — it MUST remain research-grade, never
  diagnostic (CR-5), with prominent caveats. Disease-risk + ancestry are **sensitive/dual-use**
  (privacy, consent, potential stigma/misuse) and engage the safety model
  (`documentation/explanation/safety_model.md`); over-interpretation risk is high. Likely needs an
  explicit consent/disclaimer step and may route summaries through review. The existing anti-persona
  note (clinician seeking diagnosis) and the variant→phenotype caveat (`personas.md`) apply directly.
- **Status:** backlog → **referenced on `roadmap.md` as L8 (Later, M6+ candidate)** as a directional
  theme; not yet promoted (still `idea` — batch-variant path + privacy controls are unscoped). High
  user value, high responsibility. Capture caveats in `documentation/community-notes/` as we learn.

### FC-2 — Structural & copy-number variation analysis

- **What:** beyond SNV/indel — SV/CNV detection & interpretation (incl. long-read), effects on
  genes/regulatory elements/3D structure.
- **Prereqs:** long-read/SV tooling, breakpoint-aware coordinates. **Status:** idea.

### FC-3 — Multi-omics integration

- **What:** jointly reason over genome + transcriptome + proteome + metabolome for a sample/strain;
  ties into networks/systems (FR-18d). **Status:** idea.

### FC-4 — Wet-lab / LIMS integration (design → build → test loop closure)

- **What:** optional, opt-in export/handoff of vetted designs to lab automation/LIMS; closes the
  bioengineer's loop (`personas.md` P6). Must preserve the review gate and "we recommend, we don't
  execute" boundary unless explicitly enabled. **Status:** idea (currently a v1 non-goal, §1).

### FC-5 — Real-time multi-user collaboration

- **What:** shared sessions/workspaces, presence, comments on runs/artifacts. **Status:** deferred
  (§1).

## 5. How to add to this backlog

Add an `FC-N` entry (short) when you have a credible future capability; flesh it out only when picked
up. When promoted: move it to `roadmap.md`, then write the `FR-*`, the `specs/biology/` methodology
spec, the capability subgraph, and (usually) a macro/session type. See `CONTRIBUTING.md`.

## 6. Related

`roadmap.md` · `specs/product/mission.md` · `specs/product/product_requirements.md` ·
`specs/agent/session_types.md` · `specs/training/post_training.md` ·
`documentation/community-notes/` · `CONTRIBUTING.md`.
