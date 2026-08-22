# Post-Training — Spec

> Status: Draft v0.1 — **normative contract** (forward-looking). Defines testable requirements for
> adapting the agent's **reasoning LLM** (and small auxiliary models) after pre-training. The
> narrative rationale is `documentation/explanation/post_training.md`; this document is the
> requirements it must satisfy. RFC-2119 keywords. IDs are stable: `PT-*`. Evaluation substrate:
> LangSmith (`.agents/guidelines/langsmith.md`). Model serving: `specs/services/llm_service.md`.

## 1. Scope

In scope: which models may be post-trained, data sourcing/curation/governance, training stages,
evaluation gates, and release controls for the agent's reasoning LLM and auxiliary classifiers. Out of
scope: serving (`llm_service.md`), harness behavior (`specs/agent/harness_and_context_engineering.md`),
and the domain foundation models' own training.

## 2. What may be post-trained (`PT-1`)

- **PT-1.1** The reasoning LLM (default Gemma 4 4B) MAY be post-trained for genomics tool-use,
  planning, cited writing, calibrated confidence, and safe refusal.
- **PT-1.2** Small auxiliary models (intent/risk/organism classifiers) MAY be fine-tuned/distilled.
- **PT-1.3** Domain foundation models (AlphaGenome, Evo 2, ESMFold, Boltz-2, …) MUST NOT be
  fine-tuned in-product; they are used at their released weights and are versioned, not trained
  (`external_models_and_services.md`). Any exception requires an ADR.

## 3. Data sourcing & governance (`PT-2`)

- **PT-2.1** Training data MUST derive from recorded run traces (LangSmith + internal trace) plus
  human-review decisions, critic flags, eval scores, user feedback, and labeled safety cases.
- **PT-2.2** Positive SFT examples MUST be restricted to reviewer-**approved** and/or high-eval
  trajectories; rejections and critic-caught errors MUST be used only as negatives/preferences.
- **PT-2.3** Trajectories MAY contain private sequence data; training-data use MUST comply with the
  retention/consent policy (`specs/data/*`) and MUST be de-identified where required. Data from users
  who have not consented to training use MUST be excluded.
- **PT-2.4** Provenance of each training example (source run, filters applied) MUST be retained for
  auditability and reproducibility.

## 4. Training stages (`PT-3`)

The pipeline SHOULD support, in order:

- **PT-3.1 SFT** on gold trajectories (query → intent → plan → tool calls → evidence → cited report),
  teaching correct labels, valid plans, well-formed tool calls (incl. organism-appropriate model
  choice), and citation-grounded writing.
- **PT-3.2 Tool-use/function-calling adaptation** to maximize first-try schema-valid structured output
  (reduce `HARN-3` retries), including hard negatives (wrong-organism selection, uncited claims).
- **PT-3.3 Preference optimization** (DPO/ORPO) from outcome pairs (approved vs rejected, high vs low
  eval, grounded vs hallucinated, appropriate vs over/under-refusal).
- **PT-3.4 Distillation** of a larger teacher into the local model for common session types
  (`session_types.md`), and of auxiliary classifiers into small fast models.
- **PT-3.5 Safety post-training** aligned to the threat model (`safety_model.md`), curated and
  versioned separately from capability data.
- **PT-3.6 RLVR (Reinforcement Learning with Verifiable Rewards)** — the preferred RL approach here
  (rationale + reward catalog: `documentation/explanation/post_training.md` §3.6):
  - **PT-3.6.1** RL rewards MUST come from **deterministic, versioned, unit-tested verifiers**
    (programmatic checks), NOT solely from a learned reward model. Verifiers MUST reuse the same
    validation code the harness/critic use (schema, organism rules, coordinate checks,
    entailment-based citation checks) so training and production agree
    (`harness_and_context_engineering.md` `HARN-3`, `tool_use_policy.md`, `coordinate_systems.md`).
  - **PT-3.6.2** The reward MUST combine multiple verifiers, and **safety MUST act as a gate**: any
    trajectory that fails the safety verifier MUST receive non-positive total reward regardless of
    task quality (mirrors `HARN-6`). The legitimate-dual-use reward MUST be co-optimized to prevent a
    degenerate always-refuse policy.
  - **PT-3.6.3** Citation/grounding reward MUST be **entailment/quote/accession-based** (the source
    actually supports the claim), not mere presence of a citation, to resist reward hacking.
  - **PT-3.6.4** RL rollouts MUST be **on-policy against the active HarnessAdapter through the real
    CellXP skill/policy kernel** or a
    **faithfully mocked/cached tool layer** (recorded real tool outputs), and MUST run in a
    **sandbox with no real side effects** (no actual edits/orders; actionable outputs simulated).
  - **PT-3.6.5** RL prompt/task datasets MUST be versioned and **disjoint** from eval sets (`PT-4.1`).
  - **PT-3.6.6** RLVR complements DPO (`PT-3.3`): use DPO where verification is infeasible (e.g.
    writing quality), RLVR where reward is programmatic.

## 5. Evaluation gates (`PT-4`)

- **PT-4.1** Every candidate checkpoint MUST be evaluated on a held-out suite in LangSmith before any
  promotion; eval datasets MUST NOT overlap with training data (no contamination).
- **PT-4.2** The suite MUST cover, at minimum: per-capability task correctness; **organism-appropriate
  model selection** (e.g. never AlphaGenome on bacteria); citation validity + evidence completeness;
  confidence calibration (ECE); safety recall + over-refusal rate; tool-call validity/retry rate;
  latency; cost (map to `specs/product/success_metrics.md`).
- **PT-4.3** A checkpoint MUST NOT ship if it regresses **safety recall** or **over-refusal rate**
  versus the incumbent, even if task metrics improve.
- **PT-4.4** Promotion requires beating the incumbent on the trust + safety metrics without
  regressions; results MUST be recorded.

## 6. Release & rollback (`PT-5`)

- **PT-5.1** Shipped checkpoints MUST be versioned and pinned in serving config
  (`llm_service.md`); the active model version MUST be recorded in run provenance (`FR-24`).
- **PT-5.2** A rollback path to the previous checkpoint MUST exist.
- **PT-5.3** Local-first serving MUST be preserved: a post-trained default MUST remain runnable via the
  local Ollama path (no hard dependency on a remote provider).

## 7. Implementation details (`PT-6`)

- **PT-6.1 Offline pipeline.** Post-training MUST run as a separate offline pipeline, not on the
  serving path; it consumes governed datasets (`specs/data/*`) and produces versioned
  checkpoints/adapters that `llm_service.md` serves.
- **PT-6.2 Parameter-efficient default.** Training SHOULD use **LoRA/QLoRA** adapters on the Gemma 4 4B
  base (one base, many adapters, e.g. per session type) and MAY merge for release. Full fine-tunes
  require justification (cost/benefit).
- **PT-6.3 Verifier service.** Verifiers MUST be implemented as pure deterministic functions
  `verify(prompt, trajectory) -> {score∈[0,1], reason}`, versioned and unit-tested, sharing code with
  the harness/critic (`PT-3.6.1`). Reward aggregation MUST apply safety as a multiplicative gate
  (`PT-3.6.2`).
- **PT-6.4 Rollout infra.** RLVR rollouts SHOULD use fast sampling (e.g. vLLM) and a **cached/mocked
  tool fixture store** for outcome rewards; live-tool rollouts MUST be limited and sandboxed
  (`PT-3.6.4`).
- **PT-6.5 Tooling (recommended, not mandated).** SFT/DPO via TRL/Axolotl + PEFT (+ Unsloth);
  RLVR via TRL `GRPOTrainer` (or a verifiers-style harness); evaluation via LangSmith
  (`.agents/guidelines/langsmith.md`). Framework choices are advisory; the contracts above are binding.
- **PT-6.6 Serving handoff.** Released models MUST be convertible to the local-first serving format
  (e.g. **GGUF** for Ollama) so a post-trained model drops into the existing path (`PT-5.3`); version
  pinned and recorded in provenance (`PT-5.1`).
- **PT-6.7 Reproducibility.** Each training run MUST record dataset versions, base-model version,
  hyperparameters, verifier versions, and eval results sufficient to reproduce and audit the
  checkpoint.

## 8. The flywheel (informative)

```
runs → traces → filter (review decisions + eval scores + safety labels)
     → curated, governed datasets → SFT / tool-use / DPO / distillation / safety / RLVR
     → eval gates (PT-4) → versioned release (PT-5) → more runs
```

## 9. Acceptance criteria

- A candidate cannot be promoted without a recorded LangSmith eval beating the incumbent on trust +
  safety with no safety regression (`PT-4`).
- Training datasets exclude non-consented/private-restricted data and carry per-example provenance
  (`PT-2`).
- RL reward is verifier-based with safety as a gate, verifiers are versioned/unit-tested, and RL
  prompts are disjoint from eval sets (`PT-3.6`, `PT-6.3`).
- The active model version is visible in run provenance and is rollback-capable (`PT-5`).
- No domain foundation model is fine-tuned without an ADR (`PT-1.3`).

## 10. Open questions

- LoRA/QLoRA adapters per session type vs a single merged model.
- Online/continual updates vs periodic batched releases.
- Synthetic trajectory generation (self-play over macros) and contamination controls.
- Whether auxiliary classifiers ship as distilled models in v1 or stay prompt-based.
- RLVR rollout fidelity: how much can run on mocked/cached tools before benchmark agreement degrades;
  GRPO vs PPO/RLOO; per-capability reward weights and safety-gate calibration.

## 11. Related

`documentation/explanation/post_training.md` (rationale) · `specs/services/llm_service.md` ·
`specs/agent/harness_and_context_engineering.md` · `documentation/explanation/safety_model.md` ·
`documentation/explanation/evidence_and_confidence.md` · `specs/product/success_metrics.md` ·
`specs/data/*` · `.agents/guidelines/langsmith.md`.
