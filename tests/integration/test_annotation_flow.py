"""Supervisor integration for the annotation capability subgraph (L1, FR-16)."""

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from cellxp.agent.graph import build_graph, production_capability_nodes
from cellxp.agent.subgraphs import annotation as annotation_module
from cellxp.domain.enums import IntentType, RunStatus
from cellxp.services.base import ServiceOutcome, ServiceResult
from cellxp.services.reference import EntityResolveRequest, EntityResolveResult, ResolvedEntity
from cellxp.services.reference.annotations import AnnotationFeature, AnnotationRequest, AnnotationResult
from cellxp.services.reference.genome import ReferenceGenomeService


class _Snap25AnnotationReferenceService(ReferenceGenomeService):
    def resolve_entity(self, request: EntityResolveRequest) -> ServiceResult[EntityResolveResult]:
        return ServiceResult.succeeded(
            EntityResolveResult(
                entity=ResolvedEntity(
                    identifier="SNAP25",
                    type="gene",
                    label="SNAP25",
                    organism=request.organism,
                    assembly=request.assembly or "GRCh38",
                    chrom="chr20",
                    start=30_000_000,
                    end=30_050_000,
                )
            )
        )

    def annotate(self, request: AnnotationRequest) -> ServiceResult[AnnotationResult]:
        return ServiceResult.succeeded(
            AnnotationResult(
                organism=request.organism,
                assembly=request.assembly,
                source_databases=["test_catalog"],
                features=[
                    AnnotationFeature(
                        feature_id="ENSG00000139318",
                        feature_type="gene",
                        chrom=request.chrom or "chr20",
                        start=request.start or 0,
                        end=request.end or 50_000,
                        name="SNAP25",
                        source="test_catalog",
                    )
                ],
            )
        )


def test_supervisor_dispatches_annotation_without_n3_scaffold_error() -> None:
    graph = build_graph(capability_nodes=production_capability_nodes())

    result = graph.invoke(
        {
            "user_query": "/annotate chr1:1000-2000",
            "normalized_inputs": {
                "organism": "Homo sapiens",
                "assembly": "GRCh38",
            },
        }
    )

    assert result["status"] is RunStatus.COMPLETED
    assert result["final_report"].markdown
    step_names = {step.name for step in result["steps"]}
    assert "classify_scope" in step_names
    assert "call_annotation" in step_names
    assert not any(error.kind == "CapabilityUnavailable" for error in result.get("errors", []))


def test_snap25_expression_query_with_annotation_capability() -> None:
    """Gene-named expression questions resolve locus then annotate when capability is selected."""
    nodes = production_capability_nodes()
    nodes["annotation_subgraph"] = annotation_module.build_subgraph(
        reference_service=_Snap25AnnotationReferenceService()
    )
    graph = build_graph(capability_nodes=nodes)

    result = graph.invoke(
        {
            "user_query": "annotate snap25 — is it expressed in cerebellum?",
            "normalized_inputs": {
                "organism": "Homo sapiens",
                "assembly": "GRCh38",
            },
        }
    )

    assert result["status"] is RunStatus.COMPLETED
    step_names = {step.name for step in result["steps"]}
    assert "resolve_gene_locus" in step_names
    assert "classify_scope" in step_names
    assert "call_annotation" in step_names
    assert not any(
        error.message.startswith("annotation subgraph: provide a genomic interval")
        for error in result.get("errors", [])
    )


def test_expression_query_resumes_after_annotate_capability_selection() -> None:
    """Simulates selecting 'annotate sequence' after an ambiguous expression query."""
    nodes = production_capability_nodes()
    nodes["annotation_subgraph"] = annotation_module.build_subgraph(
        reference_service=_Snap25AnnotationReferenceService()
    )
    graph = build_graph(capability_nodes=nodes, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "annotation-gene-resolve"}}

    paused = graph.invoke(
        {
            "user_query": "is snap25 expressed in cerebellum?",
            "normalized_inputs": {
                "organism": "Homo sapiens",
                "assembly": "GRCh38",
            },
        },
        config,
    )
    assert paused["__interrupt__"]
    question = paused["__interrupt__"][0].value
    annotate_option = next(
        option
        for option in question["options"]
        if option.get("value") == IntentType.ANNOTATION.value
    )

    completed = graph.invoke(
        Command(resume={"selected_option_ids": [annotate_option["id"]]}),
        config,
    )
    assert completed["status"] is RunStatus.COMPLETED
    step_names = {step.name for step in completed["steps"]}
    assert "resolve_gene_locus" in step_names
    assert "call_annotation" in step_names
