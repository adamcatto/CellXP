# Changelog

All notable changes to CellXP are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Maintenance rules:
`.agents/guidelines/changelog-guidelines.md`.

Categories: **Added**, **Changed**, **Deprecated**, **Removed**, **Fixed**, **Security**. Each
`[Unreleased]` bullet is prefixed with its land date: `- **YYYY-MM-DD** — …` (newest first within a
category).

## [Unreleased]

### Fixed
- **2026-06-23** — Fix remote dev chat submit: auto-allow `127.0.0.1` and LAN IPs in Next.js
  `allowedDevOrigins` so HMR hydrates when the UI is opened via IP (not only `localhost`).
- **2026-06-23** — Fix LAN remote chat access: proxy `/api/v1` through the Next.js dev server,
  bind the frontend to `0.0.0.0`, and stop baking loopback `NEXT_PUBLIC_API_BASE` into remote browsers.

### Changed
- **2026-06-23** — Document the no-mandatory-hosted-model policy, the local
  `alphagenome-pytorch` migration, and an honest quickstart covering API smoke, frontend preview,
  automated browser journeys, and current end-to-end browser limitations.
- **2026-06-23** — Build and import-check Evo 2's required pinned `vtx` CUDA extensions in the
  worker image after direct A100 acceptance exposed that the upstream wheel omits compiled kernels.
- **2026-06-23** — Make M1–M4 release evaluation fail closed on the overall biology floor, archive
  real deployed-API runs and review/audit acceptance with hashes, and expand public biology and
  non-sensitive safety catalogs to their documented size and coverage floors without adding private
  hazard content or fabricated scores.
- **2026-06-23** — Require real strand-oriented 30-bp genomic context for Rule Set 2 scoring and
  compose checksum-attested SpCas9 PAM enumeration, Cas-OFFinder/CFD specificity, circular-genome
  handling, and durable guide-pool selection while rejecting unsupported editor outcomes.
- **2026-06-21** — Make terminal reports explicitly disclose when an evidence-producing plan returns
  no evidence, and replace placeholder GWAS/variant integration tests with real supervisor flows.
- **2026-06-19** — Require per-entry land dates on `[Unreleased]` changelog bullets (`**YYYY-MM-DD** —`); update
  `changelog-guidelines.md`, backfill existing entries, and document the format in `CHANGELOG.md` /
  `.agents/onboarding.md`.
- **2026-06-19** — Populated `specs/planning/roadmap.md` (Draft v0.1): Now/Next/Later horizons (`N*`/`X*`/`L*`) hung off
  M0–M5, plus an "Execution waves" section sequencing the work for parallel agent sessions
  (contract-freeze → spine → fan-out). FC-1 in `future-additions.md` now cross-referenced as roadmap L8.

### Added
- **2026-06-23** — Package concrete pinned AlphaGenome 0.6.1 and Evo 2 0.6.0 SDK workers, an
  Open Targets/PLINK/SuSiE/coloc GWAS worker, and an Azimuth/CFD/Cas-OFFinder CRISPR worker with
  version/index attestations, fail-closed production readiness, deployment manifests, and opt-in
  live inference tests.
- **2026-06-23** — Add persisted artifact manifests/content, review-enforced immutable exports,
  audit-chain query/verification, and durable ordered CRISPR guide pools with optimistic revisions
  and frontend save/restore behavior.
- **2026-06-22** — Move production LangGraph start/resume/cancel execution out of FastAPI into
  dedicated Redis Streams graph executors with idempotent commands, retry/reclaim/dead-letter
  handling, durable snapshots/events, production capability composition, and compose/Kubernetes
  deployment manifests.
- **2026-06-22** — Add durable Postgres API/run persistence and LangGraph checkpoints, Redis Streams
  job transport, S3-compatible object storage, Playwright chat/clarification/review journeys, and a
  fail-closed M1–M3 release-gate report that distinguishes missing evidence from a passing gate.
- **2026-06-22** — Add the production structure worker with pinned ESMFold/Boltz-2 acquisition,
  bounded GPU inference, content-addressed PDB/mmCIF outputs, deployable manifests, complete model
  provenance, and opt-in live smoke tests.
- **2026-06-22** — Add opt-in GWAS Catalog/eQTL Catalogue adapters, typed statistical and CRISPR
  worker transports with bounded retries, honest offline fallbacks, and live smoke-test seams.
- **2026-06-21** — Add executable v1 session/run APIs with graph-backed clarification resume,
  ordered/replayable SSE, request deduplication, revision guards, reproduction, and HTTP e2e tests.
- **2026-06-21** — Add Ensembl gene/dbSNP resolution and cross-assembly mapping, strict remote
  AlphaGenome/Evo 2 worker transport, and complete model-call provenance.
- **2026-06-21** — Add PubMed/PMC retrieval, a persistent local SQLite vector index, and
  citation-preserving local RAG ingestion/retrieval composition.
- **2026-06-21** — Add linked locus and structure views plus review-safe guide-pool/off-target panes.
- **2026-06-21** — Add deterministic golden-result gate scoring for artifacts, evidence, models,
  review/clarification/refusal behavior, and composed capability order.
- **2026-06-21** — Add idempotent development bootstrap and configured Ollama model-download scripts,
  network-free regression tests, Make targets, and a maintenance guideline for evolving setup as
  dependencies, services, and model adapters land.
- **2026-06-20** — X7 model-guided inverse edit design (FR-18c, IDS-1..5): add a bounded desired-
  effect → proposal → forward-score → CRISPR-feasibility loop, weighted and Pareto candidate ranking,
  explicit partial-target gaps, compounded evidence/provenance, actionable supervisor routing through
  X6 review, normative service/subgraph specs, and deterministic service/planner/subgraph tests.
- **2026-06-20** — X6 human review enforcement (FR-25, FR-26, FR-39): wire actionable outputs to
  the audited LangGraph review interrupt before report generation, use replay-stable review IDs for
  durable approval resume, cover actionable artifacts and subtasks, and add executable strict
  defaults for genome-editing sessions with integration coverage for non-bypass behavior.
- **2026-06-20** — X5 CRISPR design (FR-15, CRS-1..5): typed guide, off-target, scoring, and edit-
  outcome contracts; registered service with an injectable backend and organism/assembly guards;
  candidate-only actionable guide/off-target artifacts with per-guide confidence and provenance;
  CRISPR subgraph orchestration; and deterministic service/subgraph tests.
- **2026-06-20** — X4 composed evidence pattern: deterministically plan variant-effect → GWAS →
  structure dependencies, record cross-subtask evidence coverage, and add planner regression tests
  plus a golden query and worked confidence-calibration example for the composed report.
- **2026-06-20** — X1 GWAS/QTL backend (FR-14, GWS-1..5, PROV-1): add the registered
  `GwasService` with typed association, LD, SuSiE fine-mapping, and coloc contracts; an injectable
  backend protocol; explicit human-resource organism/assembly guards and EMPTY/UNSUPPORTED/FAILURE
  outcomes; persisted table/locus artifacts and cited provenance; a reference-validation-first
  `gwas` subgraph; and 25 unit tests covering all operations and subgraph paths.
- **2026-06-20** — X2 literature-grounding capability (FR-20, RAG-1..5): five-operation
  `RagService` with an injectable retrieval/vector backend, explicit no-backend and zero-hit
  outcomes, reference-catalog guards, chunk/embedding provenance, resolvable evidence citation
  maps, citation-context artifacts, and a RAG subgraph with Steps on every execution path; 17 unit
  tests use mock backends and perform no external calls.
- **2026-06-19** — N7 safety M1 (FR-33, FR-34): append-only, SHA-256 hash-chained audit log;
  `AuditEntry`/`Actor` domain models with `verify()` and `_compute_entry_hash` (AL-4);
  `AuditLog` ORM table with composite indexes on `(run_id, at)`, `(session_id, at)`,
  `(event_type, at)`; `AuditRepository` with an insert-only `append()` path that threads
  `prev_hash` from the partition tail, a `query()` filter, and a `verify_chain()` walker;
  `make_risk_classifier(audit_repo)` factory wires `safety.refused` / `safety.restricted`
  audit entries on BLOCK/RESTRICT decisions with capped query digests (AL-3); full
  `human_review_gate` implementation with `review.requested` / `review.decided` /
  `actionable.emitted` audit writes ready for X6 graph wiring; 16 unit tests covering all
  AL-1..6 requirements; `build_graph(audit_repo=…)` injection point.
- **2026-06-19** — X3 structure capability (FR-18, STS-1..5, FR-24): `StructureService`
  (`services/structure/`) with an injectable `StructureBackend` protocol and three prediction
  operations — `predict_structure` (ESMFold monomer / Boltz-2 complex+ligand+NA, with
  service-derived pLDDT-style confidence bands and low-confidence spans), `predict_contacts`
  (Orca chromatin contact map), and `predict_dna_shape` (DNAshapeR track); deterministic
  transforms for task classification, ESMFold/Boltz-2 model selection, and confidence
  derivation; `structure` subgraph factory orchestrating task classification → reference
  validation (RGS-1, genomic kinds) → oracle → `structure_3d`/`contact_map`/`genome_track`
  artifacts with run-trace Steps on every path; no-backend operations return UNSUPPORTED
  rather than crashing, and pure prediction is never actionable (generative design FR-18a
  deferred to X6). 61 unit tests covering classification, model selection, confidence
  transforms, organism/assembly guards, oversized-sequence and alphabet-mismatch validation,
  artifact emission, and FR-24 run-trace completeness.
- **2026-06-19** — N6 frontend M1 (FR-21, FR-27, FR-30): TypeScript wire types mirroring the full
  REST+SSE contract; REST client (`lib/api.ts`); SSE streaming client with `applyRunEvent`
  accumulator (`lib/streaming.ts`); artifact helpers and genome coordinate utilities; UI
  primitives (Button, Card, Dialog, Tabs); full chat thread with progressive streaming — thinking
  disclosure, activity/tool-call log, artifact bubbles, clarification cards, and review-gate
  cards (CHT-1..10); chat composer with slash and `@`-mention autocomplete (CHT-2..4); genome
  browser pane v1 — Canvas-based track renderer, gene model track, variant table, pan/zoom/keyboard
  navigation, coordinate chrome (GBR-1..10); run inspector pane with steps timeline, evidence
  list, and artifact grid (FR-30); artifact pane dock with type-dispatch renderer; three-column
  resizable workspace layout with sidebar, keyboard shortcuts (WSP-1..10); app pages: `/chat`,
  `/runs/[runId]`, `/artifacts/[artifactId]`.
- **2026-06-20** — N5 variant-effect vertical slice (FR-13, AGS-1..5, BIS-1..5, FR-24):
  `AlphaGenomeService` with `ModelBackend` protocol, organism-appropriate oracle selection
  (AlphaGenome for mammalian, Evo 2 for other clades), and complete provenance on all calls;
  `BindingService` with motif-scan and binding-delta types; `variant_effect` subgraph factory
  orchestrating reference validation (RGS-1) → oracle → binding delta → run-trace Steps;
  `evidence_integrator` node replacing N3 pass-through; coordinate transforms (window framing,
  allele substitution, delta computation); 53 unit tests covering oracle routing, mock-backend
  paths, binding delta emission, validation failure paths, and FR-24 run-trace completeness.
- **2026-06-20** — N4 reference genome service (`services/reference/`): typed assembly catalog
  (GRCh38, GRCm39, E. coli K-12 MG1655, G. oxydans 621H with all five circular plasmids);
  `ReferenceGenomeService` implementing `list_supported_references`, `validate_variant`,
  `get_sequence`, `resolve_entity`, `liftover`, and `annotate` with full provenance-bearing Steps
  on every call (RGS-1..5); injectable `SequenceBackend` protocol; liftover and annotation types
  (`LiftoverSegment`, `AnnotationFeature`); 69 unit tests covering circular topology, origin-crossing
  extraction, ref-allele checks, contig alias resolution, and provenance compliance.
- **2026-06-19** — N3 core orchestration spine: deterministic input normalization, intent and early
  risk classification, entity/assembly clarification with a durable LangGraph interrupt, typed
  atomic and composed plans, dependency-aware subtask looping and budgets, injectable capability
  nodes, honest partial-failure reports, and safety/out-of-domain terminal responses.
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
