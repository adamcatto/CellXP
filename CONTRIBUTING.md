# Contributing to CellXP

CellXP is designed to be **extended by the community** — new capabilities, models,
species/strains, assays, harnesses, artifacts, and field knowledge. This guide is the map of *what
can be contributed*, *what each contribution requires*, and *roughly how to do it*. Each path points
to the authoritative spec that owns the contract.

> Status: Draft v0.1. The repo is **spec-first** (pre-implementation): today most contributions are
> specs/docs. Concrete mechanics (registries, CLIs, plugin loading) are still being designed — places
> marked **TODO (impl)** will firm up as the system is built. Don't block on them; propose against the
> contracts below.

## Ground rules (read first)

These are non-negotiable and apply to *every* contribution:

1. **Specs are contracts** (ADR-0004). Change the spec first (or alongside), then the code; if code
   and spec diverge, reconcile in the spec.
2. **Safety is non-bypassable.** Nothing may weaken the early safety gate or the human-review gate for
   actionable biology (`documentation/explanation/safety_model.md`, `specs/agent/human_review_policy.md`,
   ADR-0005, FR-25/26/33..35).
3. **Coordinates are sacred.** Organism + assembly + convention are always explicit; a silent
   coordinate error is a release blocker (`documentation/explanation/coordinate_systems.md`, NFR-3).
4. **Organism-appropriate models only.** Never apply a model outside its validated organism class
   (`specs/biology/supported_species.md`, `specs/agent/tool_use_policy.md`) — a 100% guardrail.
5. **Provenance + confidence always.** Every claim links to evidence; every prediction carries
   confidence (`documentation/explanation/evidence_and_confidence.md`, FR-22..24).
6. **Don't change the core agent spine** to add a capability — use the service+subgraph pattern
   (ADR-0003, NFR-11).
7. **Update the changelog** per `.agents/guidelines/changelog-guidelines.md`, and add tests/evals.

## Contribution types

Pick the row that matches what you want to add; follow its owning spec.

| You want to add… | Owning spec | Lands in |
|---|---|---|
| A **capability / task** | `specs/agent/capability-subgraphs/`, `specs/biology/` | `services/<name>/`, `agent/subgraphs/<name>/` |
| A **model / tool / package** | `documentation/reference/external_models_and_services.md` | a service that wraps it |
| A **species** | `specs/biology/supported_species.md` §5.1 | reference service registry |
| A **strain** | `specs/biology/supported_species.md` §5.4 | reference service registry |
| An **assay / output head** | `specs/biology/supported_assays.md` §5 | producing model's service |
| A **harness / orchestration layer** | `specs/agent/harness_and_context_engineering.md`, ADR | `agent/`, guidelines |
| A **macro** (reusable recipe) | `specs/agent/routing_policy.md` | macro registry |
| A **session type** | `specs/agent/session_types.md` | session registry |
| An **artifact / visualization** | `specs/interface/artifact_model.md` | `frontend/components/*` |
| **Evals / golden queries** | `specs/product/success_metrics.md`, `specs/evaluation/` | `evals/` |
| **Community notes / caveats** | this doc, §"Community notes" | notes area (TODO) |

### 1. New capability / task

A capability = a **service** (logic) + a **capability subgraph** (orchestration).
- **Requires:** a methodology spec in `specs/biology/` (typed inputs/outputs/models/transforms;
  `specs/biology/README.md`), a service under `services/<name>/` registered in `services/registry.py`,
  a subgraph under `agent/subgraphs/<name>/` reachable via `route_task`, selection metadata
  (`tool_use_policy.md`), and whether it's **actionable** (→ review gate).
- **How-to:** write the methodology spec → add the subgraph spec (`capability-subgraphs/`) → implement
  service + subgraph → register → add golden queries. See `specs/agent/graph_spec.md` §10.
- **Acceptance:** invokable via agent *and* API; provenance-complete, confidence-qualified output;
  no change to the top-level spine (NFR-11); golden query passes.

### 2. New model / tool / package

- **Requires:** a catalog entry (`external_models_and_services.md`) with status/access/task and the
  **curation rationale** (we keep one best open option per job — justify additions/replacements), an
  adapter inside the relevant service that maps our normalized inputs → the model's expected form,
  organism applicability, version pinning, and provenance recording.
- **How-to:** add the catalog row (and an *Excluded (superseded)* note if it replaces one) → wrap it in
  the service → declare selection metadata → add a fixture. Respect §19 "Integration contract" in the
  catalog.
- **Acceptance:** the agent can select it by task/organism; calls are versioned + provenance-complete.

### 3 & 4. New species / strain

Follow `specs/biology/supported_species.md` — **§5.1** for a species, **§5.4** for a strain (inherits
the parent species; brings its own strain-specific assembly/replicons; engineered strains carry an
edit lineage and may be workspace-scoped). Requires a registered assembly, applicability decisions,
annotation source, and coordinate fixtures (incl. circular/plasmid edge cases).

### 5. New assay / output head

Follow `specs/biology/supported_assays.md` §5: a stable versioned `key`, a full `AssaySpec`, an
output→evidence/artifact mapping with units, confidence semantics, and a golden fixture.

### 6. New harness / orchestration layer

The sanctioned stack is LangGraph → `create_agent` → deepagents → LangSmith
(`harness_and_context_engineering.md` §A4). Adding or swapping a harness layer is an **architectural
change → requires an ADR** (`documentation/adr/`) plus updates to the relevant
`.agents/guidelines/*`. Must preserve the guardrails (safety/review/coordinates/provenance) and the
explicit, audited L1 control flow.

### 7. New macro / session type

- **Macro:** a named, parameterized recipe (pre-baked plan). Add it per `routing_policy.md` (triggers,
  parameters, expanded subtasks). Macros must compose existing capabilities; they don't bypass gates.
- **Session type:** add per `session_types.md` (defaults, enabled capabilities, suggested macros,
  persona, **review posture**). Actionable-heavy types default to strict review.

### 8. New artifact / visualization

Extend the taxonomy in `specs/interface/artifact_model.md` (typed payload + units), then a renderer
per `.agents/guidelines/interactive-visualization.md`. Artifacts must link back to evidence/run
(FR-29), support export, and render confidence/uncertainty visibly.

### 9. Evals, golden queries & safety cases

High-value, low-friction contributions. Add golden queries (seeded from `user_stories.md`), rubric
cases, and **safety red-team / legitimate-dual-use** cases. These feed both CI gates and the
post-training flywheel (`documentation/explanation/post_training.md`). See
`specs/evaluation/testing_strategy.md` for which tier runs when, and
`.agents/guidelines/testing.md` for how to author tests/evals.

## Community notes (caveats & field knowledge)

Beyond formal specs, we want a lightweight place for **practical, experiential knowledge** that
doesn't fit a contract but saves everyone pain, e.g.:

- "Model X underperforms / is miscalibrated on organism class Y — prefer Z."
- "Assay A is noisy below depth N; treat low values as unknown."
- "Strain S's published assembly has a known mis-assembly around locus L."
- "Tool T's coordinates are 1-based despite the docs."

**Conventions for a note:** keep it short and specific; state the **claim**, the **evidence/source**
(link a run, paper, or issue), the **scope** (which model/organism/assay/version), and a **suggested
action**. Notes are advisory — if a note implies a contract change (e.g. dropping a model's
applicability), open a spec change too.

**Where notes live:** `documentation/community-notes/` — one markdown entry per note
(`NNNN-slug.md`), using `documentation/community-notes/TEMPLATE.md` and indexed in that folder's
`README.md`. If a note implies a contract change, also update the owning spec (applicability matrix,
catalog entry, coordinate convention, …).

> **TODO (impl).** Whether notes *also* become structured caveat fields on the catalog/species/assay
> **registry records** (so the agent can read them at runtime, e.g. to surface a caveat in an answer)
> is **not yet decided** — finalize alongside the data model. For now the markdown folder is the home.

## Workflow

1. Open an issue describing the contribution and which spec/contract it touches.
2. Make the spec change first (or alongside code); keep PRs small and reviewable
   (`.agents/skills`/`split-to-prs` if helpful).
3. Add tests/evals; update the changelog (`.agents/guidelines/changelog-guidelines.md`).
4. Ensure guardrails pass (safety, coordinates, review-gate, provenance) — these block merge.

## Related

`README.md` · `documentation/adr/` · `specs/` · `.agents/guidelines/` ·
`documentation/explanation/` · `CHANGELOG.md`.
