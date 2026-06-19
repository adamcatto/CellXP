# Post-Training Strategy

> Status: Draft v0.1 — **forward-looking**. How we adapt the agent's **reasoning LLM** (and small
> auxiliary models) to genomics agent work after pre-training. This is about the agent's *brain*
> (default Gemma 4 4B; `specs/services/llm_service.md`), **not** the domain foundation models. The
> evaluation/data substrate is LangSmith (`.agents/guidelines/langsmith.md`). This is the
> **rationale**; the normative, testable requirements are in `specs/training/post_training.md`.

## 1. Scope: what we do and do not post-train

| Model | Post-train? | Why |
|---|---|---|
| **Reasoning LLM** (Gemma 4 4B default) | **Yes** (planned) | adapt to genomics tool-use, planning, cited writing, calibrated confidence, safe refusal |
| **Auxiliary classifiers** (intent, risk, organism) | **Optionally** | small distilled models can be cheaper/faster/more reliable than prompting |
| **Domain foundation models** (AlphaGenome, Evo 2, ESMFold, Boltz-2) | **No** (use as released) | they are scientific oracles; we orchestrate, version, and trust their published weights — we don't fine-tune them in-product |

> Rationale: our value-add is **orchestration + grounding + safety**, not re-training genomics
> foundation models. Post-training targets the agent's behavior, not the science engines.

## 2. Why a 4B model can work here

The harness does the heavy lifting (`harness_and_context_engineering.md`): deterministic tools,
structured I/O, retrieval, and the review gate. The LLM mostly needs to **classify, plan, call tools
correctly, and write cited prose**. A small instruction-tuned model post-trained on *our* trajectories
can be very competitive at those bounded jobs — and runs locally/privately (`NFR-7`). Harder reasoning
can still escalate to a larger model per-role (`llm_service.md` §5).

## 3. Stages

### 3.1 Supervised fine-tuning (SFT) on agent trajectories
Curate gold trajectories — query → intent → plan → tool calls (correct model/organism) → evidence →
cited report — from LangSmith traces, filtered by reviewer approval and eval scores. Train the model
to reproduce: correct **intent/risk labels**, valid **plans** (macro vs composed), well-formed
**tool/function calls** (right model for the organism, right params), and **citation-grounded** writing.

### 3.2 Tool-use / function-calling adaptation
Specialize structured-output reliability: emit schema-valid JSON for `Intent`, `Plan`, `Clarification`,
and tool args first-try, reducing retries. Include hard negatives (wrong-organism model choice,
uncited claims) so the model learns the guardrails the harness enforces.

### 3.3 Preference optimization (DPO/ORPO)
Build preference pairs from outcomes: approved vs rejected actionable proposals, higher- vs lower-eval
reports, grounded vs hallucinated answers, appropriate-refusal vs over/under-refusal. Optimize the
policy toward the preferred behavior. Reward proxies map to `success_metrics.md`: trustworthy
resolution, citation validity, confidence calibration, safety.

### 3.4 Distillation
Distill a larger teacher's planning/writing into the small local model for the common session types
(`session_types.md`), and distill auxiliary classifiers (intent/risk) into tiny fast models.

### 3.5 Safety post-training
Explicit alignment for the threat model (`safety_model.md`): refuse genuine hazard-enabling requests,
**without** over-refusing legitimate dual-use research (target ≤5% over-refusal, 100% recall;
`success_metrics.md` D5). Safety SFT/preference data is curated and versioned separately.

### 3.6 RLVR — Reinforcement Learning with Verifiable Rewards
This is the highest-leverage stage for *this* product, because much of what we want the agent to do is
**programmatically checkable**. RLVR replaces a learned reward model (the usual RLHF source of reward
hacking) with **deterministic verifiers**: the policy samples a response/trajectory, verifiers score
it objectively, and we optimize toward higher reward (typically with **GRPO** — group-relative policy
optimization, which needs no value network and suits a 4B model on modest hardware; PPO/RLOO are
alternatives).

**Why genomics is a great RLVR domain.** Unlike open-ended chat, a large fraction of agent behavior
has a ground truth or a hard rule we can verify cheaply, and another fraction can be checked against
curated benchmarks. That gives dense, honest reward.

**Verifiable-reward catalog** (each verifier returns a score in [0,1] + a reason; rewards are
combined, see below):

| Reward | Verifier (how it's checked) | Cost |
|---|---|---|
| **Structured-output validity** | output parses against the Pydantic schema for `Intent`/`Plan`/`Clarification`/tool-args (`HARN-3`) | cheap |
| **Organism-appropriate model selection** | hard rule: e.g. AlphaGenome only for mammalian, Evo 2 for prokaryotes (`tool_use_policy.md` §4) — binary | cheap |
| **Coordinate/assembly correctness** | positions valid for the stated assembly; circular bacterial wrap handled (`coordinate_systems.md`) | cheap |
| **Tool-call validity** | tool exists, params type/range-check, organism applicability holds | cheap |
| **Plan well-formedness** | subtask DAG valid, `depends_on` satisfiable, no cycles (`state_schema.md` §6) | cheap |
| **Evidence completeness** | every substantive claim carries provenance (`evidence_integration.md`) | cheap |
| **Citation validity (grounding)** | the cited source actually supports the claim — checked by entailment (NLI) and/or accession/quote match, not mere presence of a citation | medium |
| **Benchmark agreement** | predicted direction/label matches a held-out curated benchmark (e.g. ClinVar pathogenicity, known eQTL sign, off-target sites vs measured, structure vs reference) | medium–high |
| **Safety behavior** | refuses on the red-team hazard set; does **not** refuse on the dual-use legitimate set (`safety_model.md`) | cheap |
| **Budget/format adherence** | stays within token/step budget; report format constraints met | cheap |

**Process + outcome rewards.** We reward both **step-level** correctness (each tool call valid,
organism-appropriate, schema-valid) and **trajectory-level** outcome (final answer correct, grounded,
safe). Step rewards give dense signal that helps a small model learn the multi-step agent loop; the
outcome reward keeps it honest about the end goal.

**Safety is a gate, not a term.** An unsafe trajectory receives **zero/negative** total reward
regardless of task quality — safety can't be "bought back" by being otherwise excellent. This mirrors
the harness guarantee that the safety/review gates are non-bypassable (`HARN-6`).

**Anti-reward-hacking.** Combine multiple verifiers (a response must satisfy several to score well),
prefer **entailment-based** citation checking over "has a citation" (so the model can't game grounding
by citing irrelevant DOIs), and keep a human-preference (DPO) channel for qualities verifiers can't
capture (clarity, helpfulness). Watch for degenerate strategies (e.g. always refusing to pass safety)
by always co-optimizing the legitimate-use reward.

**Curriculum.** Start with cheap deterministic verifiers (schema, organism rule, coordinates,
plan/tool validity), then add grounding/entailment, then benchmark-agreement once cheap behaviors are
solid. RLVR complements §3.3 DPO (use DPO where verification is hard, RLVR where reward is
programmatic).

## 4. The data flywheel

```
real runs → LangSmith traces → filter (reviewer decisions + eval scores + safety labels)
          → curated datasets → SFT / DPO / distillation / RLVR → eval gates → ship → more runs
```

- **Sources:** LangSmith run traces, human-review decisions (`ReviewState`), critic flags, user
  feedback, and labeled safety cases.
- **Filtering:** only approved/high-eval trajectories become positive SFT data; rejections and
  critic-caught errors become negatives/preferences.
- **Privacy:** trajectories may contain private sequence data; training data is governed by the
  retention/consent policy (`specs/data/*`) and de-identified where required. Local-first inference
  keeps raw data on-host by default.

## 5. Evaluation gates (no blind shipping)

Every candidate checkpoint is gated on a held-out eval suite in LangSmith before promotion:
- task correctness per capability (vs reference answers / `specs/biology/*` expectations),
- **organism-appropriate model selection** accuracy (e.g. never AlphaGenome on bacteria),
- citation validity + evidence-completeness,
- confidence calibration (ECE),
- safety recall + over-refusal rate,
- tool-call validity / retry rate, latency, cost.
A checkpoint ships only if it beats the incumbent on the trust + safety metrics without regressions.

## 6. Implementation details

### 6.1 Where post-training sits
A separate offline pipeline (its own repo area / jobs), **not** the serving path. It consumes governed
datasets (`specs/data/*`) and produces versioned checkpoints/adapters that `llm_service.md` can serve.
Inference stays local-first; training runs on whatever GPU box is available (a 4B model with
LoRA/QLoRA fits a single 24–48 GB GPU).

### 6.2 Parameter-efficient by default
Use **LoRA/QLoRA adapters** on the Gemma 4 4B base rather than full fine-tunes: cheap, fast to iterate,
and easy to keep one base + many adapters (e.g. per session type, `session_types.md`). Merge to a
single model for release if adapter-swap overhead isn't worth it.

### 6.3 Tooling (recommended, not mandated)
- **SFT/DPO:** TRL (`SFTTrainer`, `DPOTrainer`) or Axolotl; PEFT for LoRA; Unsloth for memory-efficient
  training of small models.
- **RLVR:** TRL `GRPOTrainer` (or a `verifiers`/`prime-rl`-style harness) with **vLLM** for fast
  on-policy rollout sampling.
- **Eval:** LangSmith datasets + evaluators (`.agents/guidelines/langsmith.md`).

### 6.4 Rollout generation for RLVR (the hard part)
RL rollouts must be **on-policy in the real environment**: the candidate model drives the actual agent
harness so it learns to act with our tools, not a toy prompt.
- **Cheap-verifier rollouts** (schema/organism/coords/plan/tool validity, safety) don't need to run
  the heavy domain models — they check the *decisions/format*, so rollouts are fast and high-volume.
- **Outcome/benchmark rollouts** that need real predictions run against a **mocked or cached tool
  layer** (record real tool outputs once into a fixture store; replay during training) to avoid
  re-invoking GPU foundation models every step. Reserve live-tool rollouts for a small, periodic set.
- Run rollouts in a **sandbox** with no real side effects (no actual edits/orders); the human-review
  gate's actionable outputs are simulated, never executed.

### 6.5 Verifier service contract
Verifiers are **pure, deterministic functions** `verify(prompt, trajectory) -> {score∈[0,1], reason}`,
versioned and unit-tested (a buggy verifier teaches the wrong thing). They reuse the **same code** the
harness/critic use (schema validators, organism rules, coordinate checks, entailment-based citation
checks) so training and production agree. Total reward = weighted combination with **safety as a
multiplicative gate** (unsafe → 0).

### 6.6 Datasets
RLVR needs **prompts/tasks** (not full gold trajectories): a curated, versioned set of queries with
any benchmark ground truth attached, balanced across capabilities, organisms, and the safety
red-team/legitimate-use split. SFT/DPO need labeled trajectories/pairs (§4). Keep RL prompt sets
**disjoint** from eval sets (`PT-4`, no contamination).

### 6.7 Serving the result
Convert the merged/adapter model to **GGUF** (llama.cpp) and serve via **Ollama** so the post-trained
model drops into the existing local-first path (`llm_service.md`); pin its version in serving config
and record it in run provenance. Keep a rollback to the prior checkpoint.

### 6.8 Auxiliary classifiers
Intent/risk/organism classifiers can be distilled into small encoders or tiny LLMs trained on the same
governed labels; they ship and version independently of the main model.

## 7. Open questions

- LoRA/QLoRA adapters per session type vs one merged model.
- How much auxiliary-classifier distillation vs prompting the main model.
- Online/continual updates vs periodic batched releases.
- Synthetic trajectory generation (self-play over macros) and its contamination risks.
- RLVR rollout cost vs fidelity: how much can run on mocked/cached tools before benchmark agreement
  degrades; how often to refresh live-tool rollouts.
- GRPO vs PPO/RLOO for a 4B agent; per-capability reward weights and the safety-gate calibration.

## 8. Related

`specs/services/llm_service.md` · `harness_and_context_engineering.md` ·
`multi_agent_architecture.md` · `.agents/guidelines/langsmith.md` · `safety_model.md` ·
`evidence_and_confidence.md` · `specs/product/success_metrics.md` · `specs/data/*`.
