# ADR-0004 — Use `specs/` as binding development contracts

- **Status:** Accepted (v0.1)
- **Date:** initial repo bootstrap
- **Related:** `specs/`, `AGENTS.md`, `CONTRIBUTING.md`, `specs/evaluation/regression_tests.md`

## Context

CellXP is a complex system: a multi-agent orchestrator, ten services, a streaming web client,
a persistence layer, and a deployment plane that targets three regimes. The system must also
be reproducible, auditable, and safe — properties that come from invariants the code must
honor across files, services, and contributors, not from convention alone.

The standard options for capturing that knowledge are:

1. **Code comments + README**. Knowledge lives next to code; it ages with the code; it is
   trivially out-of-date when refactors land; cross-cutting invariants have no canonical home.
2. **Wiki / Notion / Confluence**. External rich documents; tend to drift; not version-controlled
   with the code; CI cannot reference them; nobody reads them.
3. **ADRs alone**. Decisions are recorded but the resulting contracts (what every persisted
   evidence item must carry, what every artifact manifest must include, what the run lifecycle
   states are) have no normative home outside the decision narratives.
4. **Specs in the repo, treated as normative**. Markdown files in `specs/`, version-controlled
   with code, organized by area, with numbered requirements that other artifacts (tests, CI,
   reviews) can reference by ID.

The history that motivates option 4: most of CellXP's correctness comes from invariants like
"every coordinate-dependent call must validate against the reference assembly," "every
substantive evidence item must carry provenance," "every actionable output must be
review-gated." These are not implementation details; they're rules the implementation has
to obey.

## Decision

Treat the `specs/` tree as **the system's normative contracts**. Concretely:

- Each spec is a Markdown file with explicit **Requirements** (or invariants) tagged with a
  stable, namespaced ID — e.g. `PROV-1`, `ART-3`, `RGS-2`, `CHT-5`, `RLS-9`. Tags are unique
  per spec area and never reused.
- A code or behavior change that violates a numbered requirement is a **bug**, not a design
  conversation. Fix the code, or update the spec deliberately (with a PR that touches the
  spec, calls out the change in `CHANGELOG.md`, and addresses any cascading specs).
- Tests reference requirement IDs in their docstrings/names where applicable; CI is the
  enforcement layer for the machine-verifiable requirements. Human review enforces the rest.
- ADRs (`documentation/adr/*`) record *decisions* with context and trade-offs; specs
  (`specs/*`) record the resulting *contracts* the system must honor. ADRs are immutable
  history; specs are living contracts.
- Specs have a stable **read-order** (each area has a `README.md` index — see
  `specs/{agent,services,interface,data,serving,biology,evaluation}/README.md`) so a new
  contributor can ramp up by reading the specs in a known sequence.
- Specs precede code for new capabilities: a new capability lands as a spec PR first,
  reviewed for invariants, then as code PRs that satisfy the spec.

The `specs/` tree organizes around what the contract governs, not where the code lives:

- `specs/product/*` — mission, requirements (`FR-*`/`NFR-*`), personas, success metrics
- `specs/biology/*` — biological methodology and supported scope
- `specs/agent/*` — graph, nodes, state schema, control flow, capability subgraphs
- `specs/services/*` — service contracts (operations, provenance, failure modes)
- `specs/data/*` — persistence substrate (provenance, relational schema, object store, audit)
- `specs/interface/*` — API + SSE wire, artifact model, panes, workspace, chat, genome browser
- `specs/serving/*` — runtime topology and deployment regimes
- `specs/evaluation/*` — rubrics, golden queries, regression tests, testing strategy
- `specs/planning/*` — roadmap, milestones, risks, open questions

## Consequences

**Positive**

- Cross-cutting invariants have one canonical home; conflicts surface in PR review as spec
  changes, not silent code drift.
- New contributors (human or AI agent) can read a small set of specs and understand what
  the system promises without spelunking through code.
- Reviewing a PR becomes "does this code satisfy the specs it touches?" — a tractable
  question with a known answer source.
- The `Requirements` IDs become the API between specs and tests: a failing test that cites
  `PROV-4` is unambiguous about which contract broke.
- Generated artifacts (OpenAPI schemas, type stubs, prompt templates) all trace back to a
  spec that names what they must satisfy.

**Negative / accepted trade-offs**

- Specs have a cost: they must be written, reviewed, and maintained. Stale specs are worse
  than no specs because they lie. Mitigated by (a) keeping specs terse (most are 100–250
  lines, normative-first), (b) reviewing spec-and-code PRs together, (c) the spec README
  reading-orders making it obvious when a spec is out of date with its neighbors.
- Spec-first discipline slows the very first prototype of a new capability. Accepted: the
  prototype-as-spec is itself the design artifact, and skipping it almost always costs more
  later in refactors and review churn.
- New contributors may bounce off the spec volume. Mitigated by `AGENTS.md` and per-area
  READMEs surfacing the read-order; nobody needs to read everything to make a change.

**Out of scope (deliberately not adopted)**

- A formal IDL or schema language for the spec contracts (RFC-style, structured YAML
  requirements, etc.). Markdown with disciplined formatting is sufficient; we will revisit if
  cross-spec automation needs it.
- An external requirements-management tool (Jira/Linear-as-spec, doc-driven traceability
  matrices). The repo is the source of truth.

## Status notes

We will revisit this if (a) the spec tree grows past the point where the README-based
read-order is enough, or (b) we need machine-checkable cross-spec relationships beyond what
text and links provide (e.g. typed cross-references between requirement IDs).
