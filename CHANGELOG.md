# Changelog

All notable changes to CellXP are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Maintenance rules:
`.agents/guidelines/changelog-guidelines.md`.

Categories: **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed**, **Security**. Each
`[Unreleased]` bullet is prefixed with its land date: `- **YYYY-MM-DD** — …` (newest first within a
category).

## [Unreleased]

### Changed
- **2026-06-19** — Require per-entry land dates on `[Unreleased]` changelog bullets (`**YYYY-MM-DD** —`); update
  `changelog-guidelines.md`, backfill existing entries, and document the format in `CHANGELOG.md` /
  `.agents/onboarding.md`.
- **2026-06-19** — Populated `specs/planning/roadmap.md` (Draft v0.1): Now/Next/Later horizons (`N*`/`X*`/`L*`) hung off
  M0–M5, plus an "Execution waves" section sequencing the work for parallel agent sessions
  (contract-freeze → spine → fan-out). FC-1 in `future-additions.md` now cross-referenced as roadmap L8.

### Added
- **2026-06-19** — Feature-documentation guideline requiring every feature change to keep specs, docs, planning,
  test coverage/run instructions, indexes, and release history synchronized.
- **2026-06-19** — Wave 0 artifact domain contract (`domain/artifacts.py`): versioned manifests, bounded in-state
  references, explicit coordinate frames, progressive lifecycle and review metadata, accessible
  export guarantees, and superseding-correction links (`ART-1..8`).
- **2026-06-19** — Executable pull-request CI gates for backend lint/type/test/eval-catalog validation and frontend
  production builds, plus path-scoped Docker Compose validation and nightly eval catalog checks.
- **2026-06-19** — Persistence layer (Wave 0 contract code) implementing the data specs: content-addressed object
  store with a `file://` backend (`storage/object_store.py`, `OS-*`/`PROV-4`), the SQLAlchemy 2
  relational schema mirroring `AgentState` (`storage/models.py`, `RS-*`), and a `StateRepository`
  that round-trips an `AgentState` by `run_id` and enforces append-only history with `supersedes`
  corrections (`storage/repositories.py`, `RS-2`/`RS-3`/`PROV-2`/`PROV-3`). Cross-dialect column
  types keep the round-trip testable on SQLite while targeting Postgres 16/JSONB in production.
- **2026-06-19** — System testing strategy (`specs/evaluation/testing_strategy.md`, `TST-*`) and implementation
  guideline (`.agents/guidelines/testing.md`): tiered pyramid (static → unit → integration → contract
  → backend e2e → Playwright → golden evals → live model), path-based CI triggers, and release gates;
  cross-links from `evaluation_plan.md`, `regression_tests.md`, and `CONTRIBUTING.md`.
- **2026-06-19** — Product foundation specs: `specs/product/{mission,product_requirements,personas,user_stories,success_metrics}.md`.
- **2026-06-19** — Canonical tech stack + system architecture: `documentation/explanation/architecture_overview.md`
  (incl. §5.1 model orchestration).
- **2026-06-19** — External model/tool/data catalog: `documentation/reference/external_models_and_services.md`
  (curated, pruned, with networks & systems-biology and inverse-design sections).
- **2026-06-19** — Task & orchestration cookbook: `documentation/explanation/task_patterns.md`
  (step/atomic/macro/composed taxonomy; systems-level recipes).
- **2026-06-19** — Agent layer specs: `specs/agent/{state_schema,graph_spec,routing_policy,tool_use_policy,evidence_integration,human_review_policy}.md`.
- **2026-06-19** — Per-node specs: `specs/agent/nodes/*`.
- **2026-06-19** — Capability subgraph specs: `specs/agent/capability-subgraphs/*`.
- **2026-06-19** — Control-flow specs: `specs/agent/control-flow/*`.
- **2026-06-19** — Cross-cutting explainers: `documentation/explanation/{safety_model,evidence_and_confidence,coordinate_systems}.md`.
- **2026-06-19** — LLM service spec with local Ollama serving (default model `gemma4:4b`):
  `specs/services/llm_service.md`.
- **2026-06-19** — Streaming & progressive-disclosure protocol: `specs/interface/streaming_protocol.md`
  (collapsible "thinking" stream, activity/tool-call log, progressive artifacts, and Claude-Code-style
  option-based clarification cards with "yes, and" free-text).
- **2026-06-19** — Multi-agent architecture, harness/context engineering, and post-training explainers:
  `documentation/explanation/{multi_agent_architecture,harness_and_context_engineering,post_training}.md`.
- **2026-06-19** — Session/workspace model + session-type catalog: `specs/agent/session_types.md`.
- **2026-06-19** — Normative specs (testable requirements) for harness/context engineering and post-training:
  `specs/agent/harness_and_context_engineering.md` (`HARN-*`/`CTX-*`) and
  `specs/training/post_training.md` (`PT-*`), paired with their explanation-doc rationales.
- **2026-06-19** — Data-layer specs (persistence substrate): `specs/data/{README,provenance_model,relational_schema,
  object_storage,vector_index,audit_log}.md` — keystone provenance model (identity, versioning,
  content addressing, reproducibility, append-only history), Postgres schema mirroring `AgentState`,
  pluggable object store + vector index contracts, and an append-only tamper-evident audit log. Adds
  testable `PROV-*`/`RS-*`/`OS-*`/`VI-*`/`AL-*` requirements; reference stub
  `documentation/reference/database_tables.md` now points at the schema spec.
- **2026-06-19** — Engineering guidelines: `.agents/guidelines/{README,langgraph,langchain,deepagents,langsmith,interactive-visualization}.md`.
- **2026-06-19** — Architecture/control-flow diagram (Mermaid) added to `specs/agent/graph_spec.md`.
- **2026-06-19** — Biology methodology specs (programmatic I/O, models, transforms, outputs): filled all stubs and
  added new specs — `specs/biology/{README,variant_effect_prediction,gwas_qtl_lookup,crispr_design,
  inverse_edit_design,sequence_annotation,binding_site_prediction,structure_prediction,
  protein_function_and_design,metabolites_and_small_molecules,networks_systems_analysis,dna_origami,
  supported_species,supported_assays}.md`.
- **2026-06-19** — Community contribution guide `CONTRIBUTING.md` aggregating all extension points (capabilities,
  models/packages, species/strains, assays, harnesses, macros/session types, artifacts, evals) plus a
  "community notes/caveats" convention; linked from `README.md` and the biology reference specs.
- **2026-06-19** — Community-notes area `documentation/community-notes/` (README + TEMPLATE + first note:
  AlphaGenome-not-for-bacteria).
- **2026-06-19** — Planning structure: commitment-based split across `specs/planning/`. `roadmap.md` is a **Now / Next /
  Later** scaffold for near-term *committed* work (intentionally unfilled until the foundational specs
  land; coordinates with `milestones.md`); new `specs/planning/future-additions.md` holds the
  *uncommitted* backlog (deferred-from-v1 scope, exploratory entities, reasoning-LLM post-training
  track, and future capabilities incl. flagship **personal genome annotation**: VCF/BCF/FASTA →
  molecular effects / disease-risk / ancestry / PGx, research-grade). Both share an explicit promotion
  gate + status vocabulary. Resolves prior dangling references; `mission.md` and
  `product_requirements.md` §3 updated to point at the backlog.
- **2026-06-19** — Agent onboarding: cross-agent session bootstrap `AGENTS.md` (thin, auto-discovered) + canonical
  repo map / reading protocol / token-efficiency guide `.agents/onboarding.md`, to minimize
  start-of-session token usage.
- **2026-06-19** — This changelog and its maintenance guideline.

### Changed
- **2026-06-19** — Broadened product scope from DNA/RNA to also cover proteins and metabolites/small molecules, plus
  networks/systems-level analysis (`FR-18a/b/c/d`).
- **2026-06-19** — Expanded post-training docs/spec with an **RLVR** stage (verifiable-reward catalog, safety-as-gate,
  anti-reward-hacking) and concrete implementation details (LoRA/QLoRA, verifier service, on-policy
  rollouts with cached/mocked tools, GGUF→Ollama serving): `post_training.md` explainer + spec
  (`PT-3.6`, `PT-6`).
- **2026-06-19** — Updated product specs to reflect newer architecture: sessions/workspaces requirements
  (`FR-36..39`), progressive-streaming + option-based clarification (`FR-6`/`FR-7`), local-first
  pluggable reasoning LLM (`NFR-7`, `CR-6`), broadened out-of-domain wording (`FR-8`), new
  mission principles (private/local-first, transparent), persona/user-story coverage, and
  success-metric guardrails (organism-appropriate model selection, tool-call validity).

[Unreleased]: https://github.com/adamcatto/CellXP/compare/HEAD
