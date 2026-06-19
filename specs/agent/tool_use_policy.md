# Tool & Model Use Policy

> Status: Draft v0.1. Defines how a subtask chooses and invokes a concrete tool/model: selection
> among overlapping options, organism-appropriate oracle selection, input adaptation, async
> dispatch, fallbacks, and the per-call provenance contract. Pairs with `routing_policy.md` (which
> *capability* runs) — this is *which model within it*. Models are catalogued in
> `documentation/reference/external_models_and_services.md` (cited *catalog §N*). Implementation:
> `services/registry.py`, `services/base.py`, per-service clients, `jobs/*`.

## 1. Where model choice happens

`routing_policy.md` picks the **capability/subgraph**; this policy picks the **tool/model** the
subgraph's heavy step invokes. Selection is data-driven: each registered tool declares **selection
metadata** the planner/subgraph reads.

## 2. Selection metadata (per registered tool)

Every catalog entry exposes, via `services/registry.py`:

```python
class ToolDescriptor(BaseModel):
    key: str                      # stable id (e.g. "alphagenome", "boltz2")
    capability: list[str]         # tasks it serves (e.g. ["variant_effect","binding"])
    modality: list[str]           # dna | rna | protein | complex | small_molecule | ...
    organisms: list[str] | Literal["any"]   # applicability (e.g. ["human","mouse"] | "any")
    tier: Literal["light", "heavy"]          # compute weight → sync vs async
    fidelity: Literal["fast", "balanced", "high"]
    cost_hint: float | None       # relative cost/latency
    access: Literal["weights","oss","api","data","tool"]
    version: str
    status: Literal["P0","P1","C"]
    default_for: list[str] = []   # capabilities where this is the default
```

The planner/subgraph filters by `capability` + `modality` + `organisms`, then ranks.

## 3. Selection algorithm

For a subtask needing a model:

1. **Filter by applicability** — capability matches, modality matches the input, and
   **organism is supported** (§4). Drop inapplicable tools.
2. **Honor explicit user choice** — if the user requested a specific model/method, use it (record it);
   if invalid for the inputs, explain and ask/fallback.
3. **Prefer the declared default** (`default_for`) for the capability.
4. **Rank remaining** by: status (P0 > P1 > C) → fidelity vs budget fit → cost/latency → open access
   (weights/oss preferred over api/restricted, per catalog curation policy).
5. **Surface the choice** in the run trace; **ask the user** only when the trade-off is consequential
   and under-determined (e.g. fast-vs-high-fidelity structure for a large complex).

## 4. Organism-appropriate oracle selection (hard rule)

Model applicability is **not** uniform (`task_patterns.md` §1). The selector MUST respect each tool's
`organisms`:

- **Mammalian-trained** regulatory/effect models (e.g. **AlphaGenome**, assay/tissue heads) →
  human/mouse only. MUST NOT be auto-selected for bacteria/other clades.
- **Cross-species** models (e.g. **Evo 2**, prokaryote-capable) → default sequence oracle for
  non-mammalian organisms.
- For non-mammalian work, lean on function/structure models (ESMFold, Boltz-2, ESM-2, CLEAN) and
  genome-scale metabolic models where regulatory heads don't transfer.

If no organism-appropriate model exists for a requested capability, the subtask returns a clear
"unsupported for this organism" result (not a silently-wrong answer).

## 5. Input adaptation

Before invocation, the service shapes `normalized_inputs` into the tool's required form:
- sequence **window/context length**, alphabet, masking;
- **assembly/coordinate framing** — including circular bacterial coordinates and operon-awareness so
  a mammalian context window is never silently misapplied (`coordinate_systems.md`);
- multimer/ligand/complex specification for structure tools.
Adaptation failures (e.g. sequence too long, wrong alphabet) are validation errors with actionable
messages — never silent truncation of correctness-relevant input.

## 6. Async dispatch (heavy tools)

- `tier="heavy"` tools (GPU/large models: ESMFold, Boltz-2, genome-wide scans, search/optimization)
  dispatch as jobs (`jobs/queues.py`, `jobs/worker.py`, `jobs/gpu.py`).
- The subgraph records a `Step` with `job_id`, streams liveness (`run.status`/`step.*` events), and
  integrates results when ready — never blocking the top-level loop (`NFR-1/2`, `graph_spec.md` §9).
- `tier="light"` tools run inline.

## 7. Fallbacks & degradation

- On tool failure, consult ranked alternatives from §3; if a valid fallback exists, use it and note
  the substitution in provenance.
- If no fallback, append a recoverable `RunError`, mark the subtask `failed`, and continue with
  partial results (`NFR-6`).
- Repeated failures may trigger `routing_policy.md` §9 replanning (within `budget`).

## 8. Caching & idempotency

- Deterministic tool calls (same tool+version+params+inputs) SHOULD be cached (Redis;
  `storage/cache.py`) to avoid recompute and support reproducibility.
- Cache keys include `tool_version` so a model upgrade invalidates stale results.

## 9. Provenance contract (every call)

Every tool invocation MUST record into the `Step` + resulting `EvidenceItem`
(`state_schema.md` §8/§9): tool `key` + `version`, params, inputs used, output ref, timing, and (for
data/literature) citations. This is non-negotiable for `FR-24` and reproducibility.

## 10. Safety & actionability

- Tools whose output is actionable/generative (CRISPR design, origami, protein/sequence design,
  inverse edit design) mark their producing subtask `is_actionable` → human-review gate
  (`human_review_policy.md`, `FR-25/26`).
- Tool selection itself respects the risk gate: `risk=restrict` forces the gate even for
  borderline-actionable outputs.

## 11. Adding / swapping a tool

Register a `ToolDescriptor` + a `services/base.py`-conformant client; set `default_for` if it should
lead a capability; move any superseded tool to the catalog's *Excluded* list. No agent-graph change
required (`NFR-11`, ADR-0003). Endpoints via env (`*_SERVICE_URL`).

## 12. Open questions

- Ranking weights (fidelity vs cost) — fixed heuristic vs learned vs user-preference profile?
- When to A/B two oracles and report both vs pick one (e.g. AlphaGenome + Evo2 for human variants)?
- Per-user/org model allow-lists (licensing) — enforced here or at registry load?

## 13. Related specs

`routing_policy.md` · `state_schema.md` · `graph_spec.md` · `task_patterns.md` ·
`documentation/reference/external_models_and_services.md` · `coordinate_systems.md` ·
`human_review_policy.md`.
