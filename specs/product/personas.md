# Personas

> Status: Draft v0.1. Derives from `specs/product/mission.md`. Personas exist to ground product,
> interface, and evaluation decisions in concrete users. Each persona lists goals, context, pain
> points, what success looks like, and the requirements (`FR-*`/`NFR-*`) they most exercise. User
> stories per persona live in `specs/product/user_stories.md`.

## How to use these

When a design decision is contested, ask: *which persona does this serve, and does it match their
expertise and trust needs?* The primary personas drive v1; secondary personas constrain it.

---

## Primary personas

### P1 — Maya, the computational biologist ("power user")

- **Role/context:** PhD-level computational biologist or bioinformatician at an academic lab or
  biotech. Comfortable with the command line, Python, and genome coordinates; fluent in assemblies
  and file formats.
- **Goals:** Move fast across many tools without writing glue code; trust but verify; get
  figures and provenance she can drop into a paper or a slide.
- **Context of use:** Exploratory analysis, hypothesis triage, prepping figures, sanity-checking a
  collaborator's claim.
- **Pain points:** Tool sprawl and incompatible interfaces; redoing coordinate conversions; outputs
  with no provenance; black-box confidence.
- **What success looks like:** A correct, cited answer with an interactive artifact and a
  re-runnable trace — faster than she could assemble herself, and auditable enough that she'd cite it.
- **Trust needs:** High. Wants to inspect every tool call, version, and parameter; skeptical of
  unexplained predictions.
- **Heavily exercises:** FR-1..6, FR-13..21, FR-22..24 (evidence/provenance), FR-30..32 (runs),
  FR-36..38 (sessions/workspaces for ongoing projects), NFR-3 (coordinates), NFR-4 (reproducibility),
  NFR-7 (local-first privacy for unpublished data).

### P2 — Dev, the bench / bench-adjacent biologist ("domain user")

- **Role/context:** Molecular/synthetic biologist or geneticist who designs experiments but does not
  code much. Thinks in genes, edits, constructs, and phenotypes more than in coordinates.
- **Goals:** Get from a biological question to a concrete, trustworthy plan (e.g. candidate guides,
  a structural hypothesis) without becoming a bioinformatician.
- **Context of use:** Planning a knockout/knock-in, interpreting a variant of interest, designing a
  construct, scoping feasibility.
- **Pain points:** Doesn't know which tool/assembly to use; afraid of subtle coordinate/strand
  mistakes; needs results explained, not dumped.
- **What success looks like:** Plain-language guidance with the scary details handled and flagged;
  actionable designs presented with rationale and risks, behind a clear review step.
- **Trust needs:** Medium-high, but expressed as *clarity and guardrails* rather than raw inspection.
  Values the human-review gate and explicit warnings.
- **Heavily exercises:** FR-7 (clarifying questions), FR-9..11 (input handling/assembly inference),
  FR-15/FR-19 + FR-25/26 (actionable + review gate), FR-23 (confidence/limitations), NFR-9
  (accessibility/clarity).

### P3 — Sam, the bio-curious engineer ("builder")

- **Role/context:** Software/ML engineer entering genomics — strong with code and APIs, light on
  biology conventions. May be integrating or extending the system.
- **Goals:** Learn by doing; get correct results without deep domain ramp-up; reach the underlying
  API and structured outputs, not just the chat.
- **Context of use:** Prototyping, scripting against the API, evaluating whether to build on the
  platform, extending it with a new service.
- **Pain points:** Implicit biological assumptions; hidden state; APIs that don't match the UI's
  capabilities.
- **What success looks like:** The chat answer *and* the structured artifact/API payload behind it;
  clear contracts; a smooth path from "asked in chat" to "called the endpoint myself".
- **Trust needs:** Medium. Trusts structured outputs and explicit contracts; wants the seams visible.
- **Heavily exercises:** FR-9..12 (inputs/upload), FR-27..29 (artifacts addressable/exportable),
  CR-2/NFR-11 (contracts/extensibility), and the API surface (`specs/interface/api_contracts.md`).

### P6 — Lin, the bioengineer / genome-editing & tissue engineer ("designer-builder")

- **Role/context:** Bioengineer working on actionable design and construction — a genome-editing
  engineer designing edits/strains, a metabolic/synthetic-biology engineer engineering pathways
  (e.g. tuning *G. oxydans* for climate biotech), a protein engineer designing enzymes/binders, or a
  tissue engineer reasoning from genotype to constructs and cell-level phenotype. Operates in a
  **design → build → test → learn** loop and treats the copilot as a co-designer that takes actions,
  not just answers questions.
- **Goals:** Go from intent ("knock out this gene", "boost flux through this pathway", "design a
  binder for this target") to a vetted, buildable design with rationale, risks, and suggested
  experiments — and iterate quickly as results come back.
- **Context of use:** Strain/edit design, CRISPR knockout/knock-in and base/prime-edit strategy,
  protein/enzyme and binder design, metabolic-pathway and flux engineering, DNA-origami/nanostructure
  design, and composing these into a multi-step engineering plan with written-out design files.
- **Pain points:** Stitching design tools together by hand; uncertainty about feasibility,
  off-targets, and editing-system/organism compatibility; designs without provenance or risk
  assessment; no clean path from a proposed design to a next experiment.
- **What success looks like:** Candidate designs (guides, edited sequences, protein variants, pathway
  changes, origami layouts) generated, *composed* across steps, exported as usable files, and
  presented with confidence, risks, and proposed follow-up experiments — always behind the
  human-review gate before anything is framed as a recommendation or committed.
- **Trust needs:** High on *actionability* — cares deeply that designs are safe, feasible, and
  reproducible. Relies on the review gate and explicit risk/limitation reporting; wants to re-run and
  refine designs.
- **Heavily exercises:** FR-15 (CRISPR), FR-18a (protein function & design), FR-18b
  (metabolites/metabolic engineering), FR-18c (inverse edit design), FR-19 (origami), FR-5/FR-6
  (multi-step orchestration + artifact composition), FR-25/26 (review gate), FR-23
  (confidence/limitations), FR-31/32 (re-run/iterate), FR-36..39 (works in **genome-editing /
  strain-optimization sessions** with strict review posture), and the agentic side-effects (writing
  design files, suggesting experiments; `mission.md` §3).

---

## Secondary personas

### P4 — Dr. Okafor, the PI / reviewer ("auditor")

- **Role/context:** Principal investigator, reviewer, or collaborator who must vouch for results
  produced with the tool.
- **Goals:** Verify that a conclusion is sound, sourced, and reproducible before it leaves the lab.
- **Pain points:** Can't trust what can't be audited; needs to see assumptions and citations, not
  just conclusions.
- **What success looks like:** Open a run, follow the evidence from claim → tool call → source,
  confirm confidence and limitations.
- **Heavily exercises:** FR-22..24 (evidence/provenance), FR-30..32 (run inspection/reproducibility),
  NFR-5 (observability), safety FR-33..35.

### P5 — Priya, the platform operator ("operator")

- **Role/context:** Engineer/DevOps who deploys and runs CellXP (self-hosted or managed).
- **Goals:** Reliable, observable, secure operation; sane resource/GPU management; safe upgrades.
- **Pain points:** Opaque failures; runaway GPU costs; secret handling; non-portable deploys.
- **What success looks like:** Predictable deploys (compose/k8s from the same images), clear logs and
  metrics, graceful degradation, config via env.
- **Heavily exercises:** NFR-2 (async/throughput), NFR-5 (observability), NFR-6 (reliability),
  NFR-7 (security), NFR-8 (portability); infra under `infra/` and ops guides.

---

## Anti-personas (explicitly not our users in v1)

- **Clinician seeking diagnosis/treatment** — out of scope; outputs are research-grade (CR-5,
  FR-33..35). Caveat: variant-to-phenotype analysis. e.g. predicting Alzheimer's risk from DNA sequence / variants.
- **Bad actor seeking hazardous designs** — actively refused/escalated (safety model, FR-33).
- **General chatbot user** — off-domain requests are declined/redirected (FR-8).

## Persona → priority

| Persona | Tier | Primary value delivered |
|---|---|---|
| P1 Maya (comp bio) | Primary | Speed + auditable correctness across many tools |
| P2 Dev (bench bio) | Primary | Guided, guard-railed path to actionable plans |
| P3 Sam (engineer) | Primary | Structured outputs + clean contracts/API |
| P6 Lin (bioengineer / genome-editing & tissue engineer) | Primary | Vetted, composable, buildable designs + suggested experiments |
| P4 Okafor (PI/reviewer) | Secondary | End-to-end auditability & reproducibility |
| P5 Priya (operator) | Secondary | Reliable, observable, portable operation |
