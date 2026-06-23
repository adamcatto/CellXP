"""Unit tests for entity_resolver gene-symbol extraction (FR-4/7/11)."""

from __future__ import annotations

from cellxp.agent.nodes import entity_resolver
from cellxp.agent.state import AgentState, NormalizedInputs
from cellxp.domain.enums import IntentType


def test_expression_query_extracts_gene_symbol() -> None:
    result = entity_resolver.run(
        AgentState(
            user_query="is snap25 expressed in cerebellum?",
            intent=IntentType.ANNOTATION,
            normalized_inputs=NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
            ).model_dump(),
        )
    )
    normalized = NormalizedInputs.model_validate(result["normalized_inputs"])
    assert "SNAP25" in normalized.identifiers
    gene_entities = [item for item in result["entities"] if item.type == "gene"]
    assert any(item.label == "SNAP25" for item in gene_entities)


def test_gene_extraction_skips_when_interval_present() -> None:
    from cellxp.domain.models import GenomicInterval

    result = entity_resolver.run(
        AgentState(
            user_query="is snap25 expressed in cerebellum?",
            intent=IntentType.ANNOTATION,
            normalized_inputs=NormalizedInputs(
                organism="Homo sapiens",
                assembly="GRCh38",
                intervals=[GenomicInterval(chrom="chr20", start=0, end=1000)],
            ).model_dump(),
        )
    )
    normalized = NormalizedInputs.model_validate(result["normalized_inputs"])
    assert normalized.identifiers == []
