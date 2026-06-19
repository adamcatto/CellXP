# User Stories

> Status: Draft v0.1. Stories operationalize `personas.md` against `product_requirements.md`.
> Format: `As a <persona>, I want <capability>, so that <outcome>.` Each story has acceptance
> criteria (Given/When/Then) and traces to requirements. Stories are grouped into epics that map to
> capability domains; many double as **golden-query seeds** for `specs/evaluation/`.

Persona keys: P1 Maya (comp bio), P2 Dev (bench bio), P3 Sam (engineer), P6 Lin (bioengineer),
P4 Okafor (PI/reviewer), P5 Priya (operator).

---

## Epic A — Ask & orchestrate

### US-A1 — Natural-language query → grounded answer (P1, P2)
*As a researcher, I want to ask a DNA/RNA question in plain language, so that I get a cited,
confidence-qualified answer without assembling tools myself.*
- **Given** a well-posed in-domain query, **when** I submit it, **then** I see a streamed plan,
  live tool-call progress, and a final answer with inline citations and a confidence note.
- Traces: FR-1, FR-2, FR-5, FR-6, FR-22, FR-23.

### US-A2 — Clarify ambiguity instead of guessing (P2)
*As a bench biologist, I want the agent to ask when something is ambiguous, so that it doesn't run
the wrong analysis.*
- **Given** a query missing organism/assembly or with an ambiguous gene symbol, **when** I submit,
  **then** the agent asks a targeted clarifying question before executing consequential steps.
- Traces: FR-4, FR-7, FR-11.

### US-A3 — Decline off-domain politely (P3)
*As a user, I want clearly out-of-domain requests declined, so that I trust the tool's boundaries.*
- **Given** a request outside molecular biology, **when** I submit, **then** the agent declines and
  explains scope.
- Traces: FR-8.

### US-A4 — Answer a clarification by choosing an option (P2, P6)
*As a user, I want to resolve an ambiguity by picking from options (and optionally adding a note), so
that I can keep the run moving in one step.*
- **Given** the agent asks a clarifying question, **when** it presents selectable options with a
  recommended default, **then** I can choose one (or more) and/or add free text ("yes, and …"), and
  the run resumes from where it paused.
- Traces: FR-7, FR-6.

### US-A5 — Follow the agent's reasoning and tool activity (P1, P4)
*As a user, I want to watch the plan, reasoning, and tool calls stream in, so that I can trust and
debug the run without it feeling like a black box.*
- **Given** a running query, **when** I watch the response, **then** I see intent, a collapsible
  "thinking" view, live tool calls with input/output summaries, and artifacts that populate as they
  render — with depth opt-in.
- Traces: FR-6, FR-24.

---

## Epic B — Variant interpretation

### US-B1 — Is this non-coding variant regulatory? (P1, P2) — *golden seed*
*As a researcher, I want tissue-resolved effect predictions for a variant, so that I can judge if
it's regulatory and where.*
- **Given** an rsID/HGVS + organism+assembly, **when** I ask for its regulatory effect, **then** I
  get per-assay/tissue deltas, the nearest gene/regulatory context, a delta-track artifact, and a
  cited interpretation with confidence.
- Traces: FR-9..11, FR-13, FR-21, FR-22, FR-23, NFR-3.

### US-B2 — Compare a variant against literature/QTL (P1, P4)
*As a researcher, I want known associations alongside the prediction, so that I can corroborate it.*
- **Given** a variant, **when** I ask "what's known about this", **then** GWAS/QTL/eQTL evidence and
  citations are integrated with the prediction.
- Traces: FR-14, FR-20, FR-22.

---

## Epic C — GWAS / QTL

### US-C1 — Trait associations at a locus (P1) — *golden seed*
*As a comp biologist, I want associations + LD + fine-mapping for a locus, so that I can prioritize
candidate causal variants.*
- **Given** a locus/variant/gene + assembly, **when** I request GWAS evidence, **then** I get an
  interactive locus plot, a ranked association/credible-set table, and a summary.
- Traces: FR-14, FR-21, FR-27, FR-28.

---

## Epic D — CRISPR design (actionable, review-gated)

### US-D1 — Design guides for a knockout (P2, P1) — *golden seed*
*As a biologist, I want candidate gRNAs with on/off-target scores, so that I can choose a safe,
effective guide.*
- **Given** a target gene/region + organism+assembly, **when** I request guides, **then** I get a
  ranked, sortable guide table with on/off scores and PAM/strand context.
- **And** because this is actionable, results are presented as **candidates with rationale behind a
  human-review gate**; nothing is framed as "recommended" until I acknowledge the gate.
- Traces: FR-15, FR-25, FR-26, FR-27, NFR-3.

### US-D2 — Base/prime edit planning (P2)
*As a biologist, I want base/prime-editing options for a target, so that I can pick the right
editing modality.*
- **Given** a target + desired edit, **when** I ask, **then** I get modality-appropriate designs with
  feasibility notes, review-gated.
- Traces: FR-15, FR-25, FR-23.

### US-D3 — Inverse design: edits for a desired effect (P6, P2) — *golden seed*
*As a genome-editing engineer, I want the system to find edits that produce a desired functional
effect with minimal off-target/collateral impact, so that I don't have to hand-search the edit
space.*
- **Given** a *target effect* (e.g. "raise expression of gene X in tissue Y", "abolish this TF
  binding site", "shift splicing toward isoform Z") + organism+assembly, **when** I request edit
  design, **then** I get a ranked set of candidate edit strategies, each with predicted on-target
  effect + confidence (from forward models), a genome-wide off-target profile, editing feasibility
  (system/PAM/window/efficiency), and a collateral-effect assessment.
- **And** the search explicitly optimizes *maximize on-target effect, minimize off-target +
  collateral*; results are **candidates behind the human-review gate** until I acknowledge it.
- Traces: FR-18c, FR-13, FR-15, FR-25, FR-26, FR-23, NFR-3.

---

## Epic E — Annotation & binding

### US-E1 — Annotate a sequence/interval (P2, P3) — *golden seed*
*As a user, I want a sequence annotated with genes/regulatory features/motifs/ORFs, so that I
understand what's there.*
- **Given** a sequence or interval + organism, **when** I request annotation, **then** I get an
  annotation track artifact and a summary of notable features.
- Traces: FR-16, FR-21, FR-27.

### US-E2 — Predict TF binding / occupancy change (P1)
*As a comp biologist, I want motif/footprint/occupancy-delta predictions, so that I can reason about
regulation.*
- **Given** a sequence (± a variant), **when** I request binding analysis, **then** I get motif/track
  artifacts and, if a variant is given, predicted occupancy deltas.
- Traces: FR-17, FR-13, FR-21.

---

## Epic F — Structure

### US-F1 — Predict a structure from sequence (P1, P2) — *golden seed*
*As a researcher, I want a predicted 3D structure with per-residue confidence, so that I can form a
structural hypothesis.*
- **Given** a protein/nucleic-acid sequence, **when** I request structure, **then** a job runs and a
  confidence-colored interactive 3D artifact is returned, with low-confidence regions flagged.
- Traces: FR-18, FR-21, FR-23, NFR-1 (liveness), NFR-2 (async jobs).

### US-F2 — Chromatin contacts / DNA shape (P1)
*As a comp biologist, I want predicted contact maps / DNA shape, so that I can study 3D regulation.*
- **Given** an interval + assembly, **when** I request structure/contacts, **then** I get a contact-map
  and/or shape-track artifact.
- Traces: FR-18, FR-21.

---

## Epic G — DNA origami (actionable, review-gated)

### US-G1 — Design an origami shape (P2, P3)
*As a synthetic biologist, I want scaffold routing + staples under my constraints, so that I can
fabricate a nanostructure.*
- **Given** a target shape/constraints + scaffold, **when** I request a design, **then** I get an
  origami layout artifact and a cadnano-compatible export, **review-gated** as actionable output.
- Traces: FR-19, FR-25, FR-28.

---

## Epic H — Evidence, provenance & trust

### US-H1 — Audit a run end to end (P4, P1)
*As a reviewer, I want to trace any claim to its tool calls and sources, so that I can vouch for it.*
- **Given** a completed run, **when** I open the run inspector, **then** I see each node/tool call
  with inputs, versions, parameters, outputs, and the evidence behind each claim.
- Traces: FR-24, FR-30, NFR-5.

### US-H2 — Reproduce a prior result (P1, P4)
*As a researcher, I want to re-run a saved run with the same inputs, so that I can confirm
reproducibility.*
- **Given** a saved run, **when** I re-run it, **then** I get equivalent results (within documented
  model nondeterminism).
- Traces: FR-31, FR-32, NFR-4.

### US-H3 — Export an artifact for a paper/slide (P1)
*As a researcher, I want to export a figure and its underlying data, so that I can reuse it
elsewhere.*
- **Given** any visual artifact, **when** I export, **then** I get an image (PNG/SVG) and the
  structured data behind it, with provenance metadata.
- Traces: FR-28, FR-29.

---

## Epic I — Inputs & integration

### US-I1 — Upload a variant list / sequence file (P3, P1)
*As a user, I want to upload a file of variants/sequences, so that I can analyze my own data.*
- **Given** a supported file within size limits, **when** I upload and ask, **then** inputs are
  validated/normalized and analyzed, with clear errors for bad rows.
- Traces: FR-9, FR-10, FR-12.

### US-I2 — Call the API directly (P3) — *golden seed*
*As an engineer, I want to hit the same capability via API, so that I can script it.*
- **Given** API access, **when** I call a capability endpoint with normalized inputs, **then** I get
  the same structured result + artifact reference the chat would produce.
- Traces: FR-27, NFR-11, CR-2; contract in `specs/interface/api_contracts.md`.

---

## Epic J — Safety

### US-J1 — Refuse hazardous requests (P4, all)
*As a stakeholder, I want hazardous requests refused/escalated, so that the tool is safe by
construction.*
- **Given** a request whose primary purpose is hazardous, **when** submitted, **then** it is refused
  or escalated before execution, with explanation and (where possible) a safe alternative.
- Traces: FR-33, FR-34, FR-35.

---

## Epic K — Operations (secondary)

### US-K1 — Deploy and observe (P5)
*As an operator, I want portable deploys and observable runs, so that I can run this reliably.*
- **Given** the provided images/manifests, **when** I deploy via compose or k8s, **then** the system
  runs with env-based config, logs/metrics, and graceful degradation on service failure.
- Traces: NFR-2, NFR-5, NFR-6, NFR-7, NFR-8.

---

## Epic L — Sessions & workspaces

### US-L1 — Work in a typed session with memory (P6, P1)
*As a researcher, I want a persistent, typed workspace, so that defaults and prior work carry across
runs instead of re-stating them every time.*
- **Given** I open a *Strain optimization* session for *G. oxydans*, **when** I run several analyses,
  **then** the session applies its defaults (organism/assembly), surfaces relevant macros/capabilities,
  and keeps prior entities/artifacts/files available to later runs — while I can still override
  per run.
- Traces: FR-36, FR-37, FR-38.

### US-L2 — Strict review posture in actionable sessions (P6)
*As a genome-editing engineer, I want actionable sessions to gate broadly by default, so that nothing
buildable slips past review.*
- **Given** a *Genome editing* session, **when** any actionable output is produced, **then** it is
  review-gated under the session's strict posture, and the session cannot bypass safety.
- Traces: FR-39, FR-38, FR-25, FR-26.

---

## Coverage check (stories → key requirements)

| Capability FR | Covered by |
|---|---|
| FR-13 variant | US-B1, US-B2, US-E2 |
| FR-14 gwas | US-C1, US-B2 |
| FR-15 crispr | US-D1, US-D2 |
| FR-18c inverse edit design | US-D3 |
| FR-16 annotation | US-E1 |
| FR-17 binding | US-E2 |
| FR-18 structure | US-F1, US-F2 |
| FR-18a/b protein & metabolite | (see US-D3, capability stories TBD) |
| FR-19 origami | US-G1 |
| FR-20 rag | US-B2 |
| FR-21 visualization | US-B1, US-C1, US-E1, US-F1, US-F2 |
| FR-22..24 evidence/provenance | US-A1, US-B2, US-H1, US-H2 |
| FR-25/26 review gate | US-D1, US-D2, US-D3, US-G1 |
| FR-27..29 artifacts | US-C1, US-H3, US-I2 |
| FR-30..32 runs | US-H1, US-H2 |
| FR-33..35 safety | US-J1 |
| FR-6 progressive streaming | US-A1, US-A5 |
| FR-7 clarification (options + "yes, and") | US-A2, US-A4 |
| FR-36..39 sessions/workspaces | US-L1, US-L2 |
