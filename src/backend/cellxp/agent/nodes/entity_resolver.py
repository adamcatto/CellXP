"""Bootstrap entity resolution and consequential-parameter clarification (FR-4/7/11)."""

from __future__ import annotations

import re

from cellxp.agent.state import (
    AgentState,
    Clarification,
    ClarificationOption,
    Entity,
    NormalizedInputs,
)
from cellxp.domain.enums import IntentType

_ASSEMBLIES: dict[str, tuple[str, str]] = {
    "grch38": ("Homo sapiens", "GRCh38"),
    "hg38": ("Homo sapiens", "GRCh38"),
    "grch37": ("Homo sapiens", "GRCh37"),
    "hg19": ("Homo sapiens", "GRCh37"),
    "grcm39": ("Mus musculus", "GRCm39"),
    "mm39": ("Mus musculus", "GRCm39"),
}
_ORGANISMS: dict[str, str] = {
    "human": "Homo sapiens",
    "homo sapiens": "Homo sapiens",
    "mouse": "Mus musculus",
    "mus musculus": "Mus musculus",
    "e. coli": "Escherichia coli",
    "escherichia coli": "Escherichia coli",
    "gluconobacter oxydans": "Gluconobacter oxydans",
}
_COORDINATE_INTENTS = {
    IntentType.VARIANT_EFFECT,
    IntentType.GWAS_QTL,
    IntentType.CRISPR_DESIGN,
    IntentType.BINDING,
    IntentType.INVERSE_EDIT_DESIGN,
    IntentType.VISUALIZATION,
}


def _context_from_query(query: str) -> tuple[str | None, str | None]:
    lower = query.lower()
    for alias, (organism, assembly) in _ASSEMBLIES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return organism, assembly
    for alias, organism in sorted(_ORGANISMS.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return organism, None
    return None, None


def _context_question() -> Clarification:
    return Clarification(
        question="Which organism and reference assembly should CellXP use?",
        options=[
            ClarificationOption(
                label="Human — GRCh38", value="Homo sapiens|GRCh38", is_recommended=True
            ),
            ClarificationOption(label="Human — GRCh37", value="Homo sapiens|GRCh37"),
            ClarificationOption(label="Mouse — GRCm39", value="Mus musculus|GRCm39"),
        ],
        allow_freeform=True,
        blocking=True,
    )


def _intent_question() -> Clarification:
    return Clarification(
        question="What kind of analysis should CellXP perform?",
        options=[
            ClarificationOption(
                label="Annotate sequence", value=IntentType.ANNOTATION.value, is_recommended=True
            ),
            ClarificationOption(label="Predict structure", value=IntentType.STRUCTURE.value),
            ClarificationOption(label="Interpret variant", value=IntentType.VARIANT_EFFECT.value),
        ],
        allow_freeform=True,
        blocking=True,
    )


def run(state: AgentState) -> dict[str, object]:
    normalized = NormalizedInputs.model_validate(state.get("normalized_inputs", {})).model_copy(
        deep=True
    )
    query_organism, query_assembly = _context_from_query(state.get("user_query", ""))
    normalized.organism = normalized.organism or query_organism
    normalized.assembly = normalized.assembly or query_assembly

    if normalized.assembly is None:
        variant_assemblies = {
            variant.assembly for variant in normalized.variants if variant.assembly
        }
        if len(variant_assemblies) == 1:
            normalized.assembly = next(iter(variant_assemblies))

    entities: list[Entity] = []
    if normalized.organism:
        entities.append(
            Entity(
                type="organism",
                label=normalized.organism,
                organism=normalized.organism,
                assembly=normalized.assembly,
                resolved=normalized.assembly is not None,
            )
        )
    for identifier in normalized.identifiers:
        entity = Entity(
            type="variant" if identifier.lower().startswith("rs") else "gene",
            label=identifier,
            organism=normalized.organism,
            assembly=normalized.assembly,
            resolved=False,
        )
        entities.append(entity)
    for variant in normalized.variants:
        entities.append(
            Entity(
                type="variant",
                label=f"{variant.chrom}:{variant.pos + 1}:{variant.ref}>{variant.alt}",
                organism=normalized.organism,
                assembly=normalized.assembly or variant.assembly,
                resolved=bool(normalized.organism and (normalized.assembly or variant.assembly)),
            )
        )
    for interval in normalized.intervals:
        entities.append(
            Entity(
                type="interval",
                label=f"{interval.chrom}:{interval.start + 1}-{interval.end}",
                organism=normalized.organism,
                assembly=normalized.assembly,
                resolved=bool(normalized.organism and normalized.assembly),
            )
        )

    intent = IntentType(state.get("intent", IntentType.AMBIGUOUS))
    clarifications: list[Clarification] = []
    if intent is IntentType.AMBIGUOUS:
        clarifications.append(_intent_question())
    elif intent in _COORDINATE_INTENTS and not (normalized.organism and normalized.assembly):
        clarifications.append(_context_question())

    update: dict[str, object] = {"normalized_inputs": normalized, "entities": entities}
    if clarifications:
        update.update({"clarifications": clarifications, "status": "awaiting_input"})
    return update
