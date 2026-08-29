# Risks

> Status: Draft v0.1. **Top-risk register** for CellXP — the things that could materially
> derail the project, ordered by severity × likelihood. Each risk has a mitigation, a watch
> signal, and an owner-area. Risks evolve; this is a living document reviewed at each
> milestone gate. Distinct from `open_questions.md` (unresolved decisions, not threats) and
> from per-spec failure modes (mechanism-level, not project-level).

## How risks are tracked

Each risk has:

- **Severity (S)** — what it costs if it materializes: 1 (mild) to 5 (project-ending).
- **Likelihood (L)** — how probable it is in the next two milestones: 1 (rare) to 5 (near
  certain at current trajectory).
- **Mitigation** — what we're already doing or will do.
- **Watch signal** — the concrete metric / observation we monitor.
- **Owner area** — which spec / code area takes the lead.

Score (S × L) is informational, not a sort key — high-severity low-likelihood risks
(category R1) still get explicit mitigations because the cost of materializing is
catastrophic.

## R1 — Safety failure (hazard miss or gate bypass)

- **S 5 / L 2**
- **Description.** The system produces actionable output that materially uplifts a
  hazardous workflow, OR an actionable artifact ships without passing the review gate.
  Reputational and legal consequences dominate; this is the existential risk.
- **Mitigation.**
  - Structural review gate (`ADR-0005`), independent of LLM behavior.
  - Early classification (`risk_classifier`) before any capability fires
    (`safety_rubric.md` D4).
  - Audit log records every actionable artifact decision (`specs/data/audit_log.md`).
  - Safety rubric run pre-release with zero tolerance for D1/D3 misses
    (`success_metrics.md` D5).
  - Strict review posture default for genome-editing / strain-optimization / DNA-nanotech
    sessions (`session_types.md`).
- **Watch signal.** Any D1 or D3 score of 0 in evaluation; any audit-log gap on an
  actionable artifact; any user-reported gate bypass.
- **Owner area.** `documentation/explanation/safety_model.md`,
  `specs/agent/human_review_policy.md`, `specs/evaluation/safety_rubric.md`.

## R2 — Coordinate / assembly / strand correctness regression

- **S 5 / L 3**
- **Description.** A bug introduces silent coordinate, strand, or assembly errors —
  off-by-one, GRCh37/GRCh38 mix, strand-flipped functional claim, circular bacterial
  origin-cross dropped. The worst outcome is "subtly wrong answer the user trusts."
- **Mitigation.**
  - Reference service is the single source of truth (`RGS-1..RGS-5`).
  - 0-based half-open internal convention; labels on every coordinate display
    (`coordinate_systems.md`).
  - Coordinate validation tests are P0 (`regression_tests.md`).
  - Biological-correctness rubric D2 = 0 is a release blocker
    (`biological_correctness_rubric.md`).
  - Coordinate-error rate target = 0 (`success_metrics.md` D1).
- **Watch signal.** Any D2 = 0 in evaluation; any test failure in
  `tests/unit/test_coordinate_validation.py` series; any user-reported coordinate bug.
- **Owner area.** `specs/services/reference_genome_service.md`,
  `documentation/explanation/coordinate_systems.md`.

## R3 — Provenance / reproducibility erosion

- **S 4 / L 3**
- **Description.** Claims accumulate without complete provenance. Reproducing a run
  later fails. Trust collapses one citation at a time: a user clicks a citation, it
  doesn't resolve, and the system's credibility takes the hit.
- **Mitigation.**
  - Append-only `Step` / `EvidenceItem` / `ArtifactRef` records (`PROV-1..PROV-7`).
  - Provenance completeness ≥ 95% as a gate metric (`success_metrics.md` D2).
  - Citation validity ≥ 95% on RAG outputs.
  - Reproducibility-rerun harness for deterministic steps (`PROV-6`).
  - `biological_correctness_rubric.md` D4 = 0 is a release blocker.
- **Watch signal.** Provenance completeness dropping below threshold; citation-resolve
  failures in RAG eval; any reproduction-rerun divergence on deterministic queries.
- **Owner area.** `specs/data/provenance_model.md`,
  `documentation/explanation/evidence_and_confidence.md`.

## R4 — Model selection drift on organism / assay boundaries

- **S 4 / L 3**
- **Description.** The agent silently calls a model outside its declared support — e.g.
  AlphaGenome assay heads on a bacterial genome, ESMFold on a complex requiring multimer
  prediction. Output looks plausible; it isn't.
- **Mitigation.**
  - `tool_use_policy.md` §4 organism-appropriate model selection.
  - Service-side enforcement (`AGS-1`, mammalian-only refusal in
    `specs/services/binding_service.md`).
  - `biological_correctness_rubric.md` D3 = 0 is a release blocker.
  - Organism-appropriate model selection target = 100%
    (`success_metrics.md` D1).
- **Watch signal.** Any D3 = 0 in evaluation; any service-side "unsupported organism"
  refusal converted to a silent fallback.
- **Owner area.** `specs/agent/tool_use_policy.md`, per-service `*_service.md` specs.

## R5 — Agent-harness or compatibility-runtime churn

- **S 3 / L 4**
- **Description.** A Qwen Code SDK/event/permission change or a LangGraph compatibility update
  breaks adapter streaming, skill discovery, checkpoints, or interrupt semantics.
- **Mitigation.**
  - Domain logic and policy remain behind harness-neutral typed skills (ADR-0008).
  - Pin harness/runtime releases and contract-test event, permission, cancellation, and resume
    fixtures before upgrades.
  - Integration tests cover skill-policy enforcement and compatibility graph checkpoint parity.
- **Watch signal.** Harness release notes flagging stream/SDK/hook/permission changes; LangGraph
  interrupt/checkpoint changes; any adapter contract failure on an upgrade PR.
- **Owner area.** `specs/agent/*`, `src/backend/cellxp/harness/`.

## R6 — Local-first regression (creep toward cloud-required defaults)

- **S 4 / L 2**
- **Description.** A feature is built assuming hosted Postgres / hosted vector / hosted
  LLM / cloud object store; regime 1 breaks. The "private sequence data never leaves
  host" promise (`NFR-7`) silently weakens.
- **Mitigation.**
  - Pluggable backends are normative (`NFR-11`, `serving/README.md`).
  - Regime 1 smoke test required for every milestone (M0 onward).
  - "Switching to a hosted provider is an explicit, audit-logged choice"
    (`llm_service.md` §8, `chat_interface.md` §11).
- **Watch signal.** Any PR adding a hosted-only path; any regime-1 smoke-test failure;
  any user-facing string referencing a cloud service as required.
- **Owner area.** `specs/serving/*`, `.env.example`, `specs/data/object_storage.md`.

## R7 — Pane / artifact taxonomy sprawl

- **S 3 / L 3**
- **Description.** Each new capability adds one-off "ad-hoc artifact" shapes and bespoke
  panes that aren't part of the registry. The interface fragments; cross-pane sync breaks;
  accessibility drifts.
- **Mitigation.**
  - `artifact_model.md` §4 catalog is the only allowed source of artifact types.
  - `interactive_panes.md` §4 pane manifest is required for every new pane.
  - Code review enforces "no one-off JSON blobs" and "no bespoke renderer outside the
    registry."
- **Watch signal.** PRs adding artifact types without registry entries; pane components
  that don't ship a manifest; visualization service operations whose outputs don't
  conform to a registered type.
- **Owner area.** `specs/interface/{artifact_model,interactive_panes}.md`,
  `.agents/guidelines/interactive-visualization.md`.

## R8 — GPU / cost overrun in regime 2 or 3

- **S 3 / L 3**
- **Description.** Boltz-2 / RFdiffusion / large-LLM serving consumes more GPU than
  budgeted. Cost or queue saturation makes the product unusable.
- **Mitigation.**
  - Per-class queues + warm-load policy (`domain_model_serving.md` §6).
  - Per-run `Budget` cap with budget-replan node
    (`state_schema.md` §15, `control-flow/replanning_and_budget.md`).
  - Per-tenant capacity caps in regime 3 (`agent_runtime_serving.md` §6).
  - Hosted-API LLM fallback as an opt-in capacity valve
    (`reasoning_llm_serving.md` §5).
- **Watch signal.** Queue depth growth without proportional throughput; per-run cost
  exceeding budget; HPA saturation.
- **Owner area.** `specs/serving/{domain_model_serving,agent_runtime_serving}.md`.

## R9 — Native macOS port slip

- **S 2 / L 3**
- **Description.** Porting the web client to native macOS (Tauri-first per
  `frontend_deployment.md` §6) takes longer than expected because of Mol\* / Canvas
  performance gaps or sandbox issues. M5 slips.
- **Mitigation.**
  - Web client is the canonical client; macOS is a port, not a replacement.
  - Tauri choice minimizes porting risk (web-tech UI reuse).
  - Fallback intermediate ship: macOS chrome around a web view; full native renderers
    later.
- **Watch signal.** Mol\* / pane render benchmarks failing macOS targets; sandbox
  blockers on the file/upload paths.
- **Owner area.** `specs/serving/frontend_deployment.md`.

## R10 — Eval over-fit

- **S 3 / L 3**
- **Description.** The agent (or its prompts/post-training) starts to over-fit the
  published golden set. Pass rates rise without real biological-correctness improvement.
- **Mitigation.**
  - Golden set is shape-based, not exact-match (`golden_query_sets.md` §9).
  - Golden set refreshed periodically (`golden_query_sets.md` §8.4).
  - Held-out subset never used during prompt iteration or post-training.
  - Real-usage TRR ≥ 0.6 target (`success_metrics.md` §1) is the corroborating signal.
- **Watch signal.** Golden pass-rate ↑ while real-usage TRR / rework-rate stagnates;
  scorer reports of "answers feel templated."
- **Owner area.** `specs/evaluation/*`, `specs/training/post_training.md`.

## R11 — Spec drift / stale-spec hazard

- **S 3 / L 3**
- **Description.** Code evolves; specs don't. Contributors (human or AI) follow the spec
  and get the wrong answer. The "specs as contracts" discipline (`ADR-0004`) fails
  silently.
- **Mitigation.**
  - Spec changes are part of the same PR as code changes that touch the affected
    contract.
  - Per-area READMEs surface read-order; out-of-order specs are visible.
  - Periodic spec review (each milestone gate) catches stale areas.
- **Watch signal.** PRs that change code in `services/` / `agent/` / `interface/`
  without spec edits; per-spec `Status` headers that haven't moved in two milestones.
- **Owner area.** `ADR-0004`, per-area `specs/*/README.md`.

## R12 — Reasoning-LLM serving bottleneck (sub-agent fan-out)

- **S 3 / L 2**
- **Description.** As sub-agent fan-out grows, Ollama's serial-per-model throughput
  becomes the bottleneck; latency degrades; switching to vLLM is forced before the
  workstation deployment is ready.
- **Mitigation.**
  - `OLLAMA_NUM_PARALLEL` knob + agent-side `max_concurrent` budget
    (`reasoning_llm_serving.md` §3.4, `RLS-9`).
  - `LLM_PROVIDER` pluggability; vLLM opt-in well-documented.
  - Per-role overrides off by default in regime 1 to avoid model swap thrash.
- **Watch signal.** Sustained `activity.update` "waiting for LLM slot" events;
  time-to-first-token p95 trending up.
- **Owner area.** `specs/services/llm_service.md`,
  `specs/serving/reasoning_llm_serving.md`.

## R13 — Single-maintainer / bus-factor

- **S 4 / L 3**
- **Description.** Project knowledge concentrates in one person; loss of that person
  blocks substantial work.
- **Mitigation.**
  - `specs/` as the durable source of truth (`ADR-0004`) — knowledge survives in the
    repo, not in heads.
  - `AGENTS.md` and per-area READMEs onboard new contributors.
  - Use of AI coding agents as documented contributors (the specs anchor their work).
- **Watch signal.** Areas of the code where only one contributor has touched in the last
  N PRs; specs that haven't been read by anyone else.
- **Owner area.** organizational, not technical; addressed via documentation and tooling.

## R14 — Privacy egress breach

- **S 5 / L 1**
- **Description.** Private sequence data leaks to a hosted provider without user consent
  — a bug, a missing consent gate, a CDN buffering issue, or a misconfigured deployment.
- **Mitigation.**
  - Local-first default (`NFR-7`).
  - Hosted-provider use is an explicit, audit-logged choice with UI consent gate
    (`llm_service.md` §8, `chat_interface.md` §11).
  - Safety rubric D5 = 0 is a release blocker (`safety_rubric.md`).
  - SSE / API path inspection: no biological payloads in logs, notifications, or
    third-party telemetry (`API-9`).
- **Watch signal.** Any safety-rubric D5 = 0; user reports of unconsented hosted-provider
  use; CDN config drift.
- **Owner area.** `specs/serving/*`, `specs/services/llm_service.md`,
  `specs/data/audit_log.md`.

## R15 — Scope creep into mobile / clinical / wet-lab control

- **S 3 / L 2**
- **Description.** Pressure to ship features explicitly out-of-scope per
  `product_requirements.md` §3 (mobile-native, clinical use, wet-lab hardware control)
  diverts effort and weakens the v1 focus.
- **Mitigation.**
  - `future-additions.md` §1 explicitly tracks these as deferred.
  - Roadmap promotion rules require scoping + prereqs before commitment.
  - Mission and PRD are the canonical scope contract.
- **Watch signal.** PRs adding mobile-only paths, clinical-grade framing, or hardware
  integration without a roadmap promotion record.
- **Owner area.** `specs/product/{mission,product_requirements}.md`,
  `specs/planning/roadmap.md`.

## Cross-risk patterns

A few recurring patterns worth naming explicitly:

- **Silent-failure dominance.** R2, R3, R4, R14 all share the property that the worst
  outcome is a wrong-but-plausible answer (or quiet egress) the user doesn't notice. The
  rubric-based release gates (`success_metrics.md` D1/D2/D5) are the primary structural
  defense.
- **Discipline-cost risks.** R7, R10, R11 are all "the discipline that makes this work
  stops being practiced." Mitigated structurally (registries, manifests, README read-
  orders) so the easy path is the right path.
- **Dependency-evolution risks.** R5, R9, R12 share an upstream-software-changes shape.
  The mitigation in all three is isolation (harnesses behind adapters/skills, Mol\* behind a viewer
  contract, LLM behind a provider interface) so a forced swap is local rather than systemic.

## Review cadence

- **Per milestone gate.** Re-rate every risk's L and adjust mitigations; close risks that
  have been structurally addressed; add new ones surfaced during the milestone.
- **Per safety incident** (any D1 = 0 in evaluation or production): immediate review of
  R1 and any adjacent risks; corrective action recorded in the audit log AND in the next
  release's CHANGELOG.

## Open questions

- Whether to add a separate "biological dual-use governance" risk distinct from R1, or
  keep them folded (current bias is to fold; safety_model.md is one policy).
- Whether to publicly publish the (redacted) risks register at each release for user
  transparency.
- A formal severity-likelihood matrix vs the per-risk written reasoning we use today
  (which scales better but is less skimmable).

## Related

`specs/planning/roadmap.md` · `specs/planning/milestones.md` ·
`specs/planning/open_questions.md` · `specs/planning/future-additions.md` ·
`specs/product/{mission,product_requirements,success_metrics}.md` ·
`specs/evaluation/{biological_correctness_rubric,safety_rubric,evaluation_plan}.md` ·
`documentation/explanation/safety_model.md` · `ADR-0001` through `ADR-0005`.
