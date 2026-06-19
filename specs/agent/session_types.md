# Session Types (Workspaces)

> Status: Draft v0.1. Defines the **session / workspace** concept and the catalog of session types.
> A session is the durable container a user works in; it shapes defaults, context/memory, macros,
> tools, and review posture. Relates to: `specs/interface/workspace_interface.md` (UI),
> `routing_policy.md` (macros), `state_schema.md` (runs), `harness_and_context_engineering.md`
> (memory), `personas.md`.

## 1. Concept

> **Yes — there are session types, and they behave like workspaces.**

A **session** (a.k.a. workspace) is a persistent project space scoped to a goal. It outlives any
single query: a user opens (say) a *Strain Optimization* session for *G. oxydans* and runs many
queries inside it over days. The session accumulates state and biases the agent toward the right
tools, organism, macros, and safeguards.

Hierarchy:

```
Session (workspace, durable)
 ├── carries: type, organism/assembly defaults, persona, entities, artifacts, files, memory, defaults
 └── contains many Runs (threads)        ← each Run is one user turn → graph execution (state_schema.md)
        └── each Run has Subtasks → Steps
```

A **run** is one execution of the agent graph (`state_schema.md`, keyed by `run_id`). A **session**
groups runs and persists context between them (`session_id`).

## 2. What a session carries

```python
class Session(BaseModel):
    id: str                                   # session_id
    type: SessionType                         # see §4 catalog
    title: str
    organism: str | None = None               # default organism for runs (e.g. "G. oxydans")
    assembly: str | None = None               # default assembly/coordinate frame
    persona: str | None = None                # default persona (personas.md), affects verbosity/UI
    default_macros: list[str] = []            # macros surfaced/auto-suggested (routing_policy.md)
    enabled_capabilities: list[str] = []      # capability subgraphs relevant to this type
    entities: list[str] = []                  # pinned/resolved entity ids (cross-run memory)
    artifacts: list[str] = []                 # accumulated artifact ids
    files: dict[str, str] = {}                # workspace virtual filesystem refs (deepagents backend)
    memory_ref: str | None = None             # durable store key (cross-session recall)
    review_posture: Literal["standard", "strict"] = "standard"
    created_at: str
```

Persistence: relational row + a **store backend** for memory and a **filesystem backend** for files
(`deepagents` `StoreBackend`/`FilesystemBackend`; `.agents/guidelines/deepagents.md`,
`specs/data/*`). The session is the unit of cross-run context engineering
(`harness_and_context_engineering.md` §B3).

## 3. How a session shapes a run

When a run starts inside a session, the session **pre-loads context and biases routing**:

1. **Defaults injection** — organism/assembly/persona seed `normalized_inputs`/UI so the user needn't
   re-state them (still overridable per run; clarification only when genuinely ambiguous).
2. **Macro priors** — `default_macros` get priority in plan selection (`routing_policy.md` §5–§6).
3. **Capability scoping** — `enabled_capabilities` focus tool selection (others remain available).
4. **Memory** — pinned entities + prior artifacts/files are available to retrieval/planning.
5. **Review posture** — `strict` forces the human-review gate on a broader set of outputs
   (`human_review_policy.md`).

Sessions never *weaken* safety: a session cannot disable the safety gate or auto-approve actionable
biology (`safety_model.md`, ADR-0005).

## 4. Session type catalog

Each type ships defaults; users can customize. (Capabilities ref `capability-subgraphs/*`; macros are
illustrative, defined in `routing_policy.md`/the macro registry.)

| Type | Goal | Default capabilities | Typical organism | Persona | Review posture |
|---|---|---|---|---|---|
| **Variant interpretation** | explain variants' effects + clinical/trait context | variant_effect, gwas, binding, annotation, rag | human | clinical/researcher | standard |
| **Genome editing** | design edits to achieve an effect with minimal off-target | crispr, variant_effect (inverse design), binding, structure, rag | any | bioengineer | **strict** |
| **Strain optimization** | improve a microbial strain's output/phenotype | annotation, variant_effect (Evo 2), systems (GRN/metabolic), crispr, rag | prokaryote (e.g. *G. oxydans*) | bioengineer/metabolic | **strict** |
| **Structure & binding** | predict structure/complexes & binding | structure, binding, rag, visualization | any | structural/researcher | standard |
| **Annotation & discovery** | annotate sequences/genomes; find features/BGCs | annotation, binding, rag, visualization | any (incl. prokaryote) | researcher | standard |
| **DNA nanotech** | design DNA-origami nanostructures | origami, structure, visualization | n/a (synthetic) | bioengineer | **strict** |
| **Literature / hypothesis** | ground questions in literature; form hypotheses | rag, visualization | any | any | standard |

> The **actionable** session types (genome editing, strain optimization, DNA nanotech) default to
> `strict` review posture because they routinely produce buildable/wet-lab outputs.

## 5. Session types ↔ composed tasks

Session types are the *workspace* framing; **macros** and **composed/systems-level tasks**
(`task_patterns.md`) are the *execution* framing. A Strain Optimization session naturally hosts the
variant→metabolism and strain-engineering recipes (`task_patterns.md` §3–§6); a Genome Editing session
hosts the inverse-design loop (`FR-18c`). The session pre-selects which of these are one click away.

## 6. UI surface

The workspace UI (`specs/interface/workspace_interface.md`) renders a session as a persistent space:
session switcher, pinned entities/artifacts panel, the file/scratchpad view, session-scoped history of
runs, and a "new run" composer pre-filled with session defaults. Session creation can be explicit
(user picks a type) or inferred from the first query (with a confirmation).

## 7. Open questions

- Inferred vs explicit session typing on first query; can a session change type mid-life?
- Default organism/assembly conflict handling when a run contradicts session defaults.
- Memory scope: what persists across sessions for a user vs stays session-local (privacy).
- Whether a cross-session "project manager" agent coordinates related sessions
  (`multi_agent_architecture.md` §7).

## 8. Related

`specs/interface/workspace_interface.md` · `routing_policy.md` · `task_patterns.md` ·
`state_schema.md` · `human_review_policy.md` · `personas.md` ·
`harness_and_context_engineering.md` · `.agents/guidelines/deepagents.md`.
