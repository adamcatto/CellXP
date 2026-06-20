"""Controlled intent classification with a deterministic local fallback (FR-2)."""

from __future__ import annotations

from cellxp.agent.state import AgentState, NormalizedInputs
from cellxp.domain.enums import IntentType, SequenceAlphabet

_RULES: tuple[tuple[IntentType, tuple[str, ...]], ...] = (
    (IntentType.INVERSE_EDIT_DESIGN, ("inverse design", "desired effect", "design an edit")),
    (IntentType.CRISPR_DESIGN, ("crispr", "guide rna", "grna", "base edit", "prime edit")),
    (IntentType.GWAS_QTL, ("gwas", "qtl", "fine-map", "finemap", "colocal")),
    (IntentType.ORIGAMI, ("dna origami", "cadnano", "staple strand")),
    (IntentType.STRUCTURE, ("structure", "fold", "contact map")),
    (IntentType.BINDING, ("binding site", "motif", "footprint", "occupancy")),
    (IntentType.ANNOTATION, ("annotate", "annotation", "gene finding", "identify this sequence")),
    (IntentType.SYSTEMS_ANALYSIS, ("metabolic network", "regulatory network", "flux", "pathway")),
    (IntentType.LITERATURE, ("literature", "papers", "pubmed", "cite sources")),
    (IntentType.VISUALIZATION, ("visualize", "plot", "genome browser", "show track")),
    (IntentType.VARIANT_EFFECT, ("variant", "regulatory effect", "pathogenic", "allele")),
)
_OUT_OF_DOMAIN = (
    "weather forecast",
    "write a poem",
    "stock price",
    "football score",
    "sort this list",
)


def classify_intents(state: AgentState) -> list[IntentType]:
    query = state.get("user_query", "").lower()
    normalized = NormalizedInputs.model_validate(state.get("normalized_inputs", {}))
    if any(phrase in query for phrase in _OUT_OF_DOMAIN):
        return [IntentType.OUT_OF_DOMAIN]

    intents = [intent for intent, phrases in _RULES if any(phrase in query for phrase in phrases)]
    if normalized.variants or any(
        identifier.lower().startswith("rs") for identifier in normalized.identifiers
    ):
        if IntentType.VARIANT_EFFECT not in intents:
            intents.append(IntentType.VARIANT_EFFECT)
    if normalized.sequences and not intents:
        alphabets = {sequence.alphabet for sequence in normalized.sequences}
        intents.append(
            IntentType.STRUCTURE if SequenceAlphabet.PROTEIN in alphabets else IntentType.ANNOTATION
        )
    return intents or [IntentType.AMBIGUOUS]


def run(state: AgentState) -> dict[str, IntentType]:
    """Set the primary intent; the planner reuses all matched intents for composition."""
    return {"intent": classify_intents(state)[0]}
