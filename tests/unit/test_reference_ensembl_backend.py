"""Network-free contract tests for the Ensembl reference backend (RGS-3)."""

from __future__ import annotations

import httpx

from cellxp.domain.enums import Strand
from cellxp.domain.models import GenomicInterval
from cellxp.services.base import ServiceOutcome
from cellxp.services.reference import (
    EnsemblRestBackend,
    EntityResolveRequest,
    LiftoverRequest,
    ReferenceGenomeService,
)


def _backend(handler) -> EnsemblRestBackend:
    client = httpx.Client(
        base_url="https://ensembl.test",
        transport=httpx.MockTransport(handler),
    )
    return EnsemblRestBackend(client=client, version="test-release")


def test_resolves_ensembl_gene_symbol_with_zero_based_coordinates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/xrefs/symbol/homo_sapiens/BRCA2":
            return httpx.Response(200, json=[{"id": "ENSG00000139618"}])
        assert request.url.path == "/lookup/id/ENSG00000139618"
        return httpx.Response(200, json={
            "id": "ENSG00000139618", "display_name": "BRCA2", "object_type": "Gene",
            "assembly_name": "GRCh38", "seq_region_name": "13", "start": 32315086,
            "end": 32400268, "strand": 1,
        })

    service = ReferenceGenomeService(entity_backend=_backend(handler))
    result = service.resolve_entity(EntityResolveRequest(
        identifier="BRCA2", organism="Homo sapiens", assembly="GRCh38",
    ))

    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None and result.value.entity is not None
    assert result.value.entity.start == 32_315_085
    assert result.value.entity.end == 32_400_268
    assert result.value.entity.strand is Strand.PLUS
    assert result.steps[0].tool_version == "test-release"
    assert result.evidence[0].provenance.tool == "ensembl_rest"


def test_resolves_dbsnp_mapping_for_requested_assembly_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/variation/homo_sapiens/rs699"
        return httpx.Response(200, json={"mappings": [
            {"assembly_name": "GRCh37", "seq_region_name": "1", "start": 1, "end": 1,
             "strand": 1, "allele_string": "A/G"},
            {"assembly_name": "GRCh38", "seq_region_name": "1", "start": 230710048,
             "end": 230710048, "strand": 1, "allele_string": "A/G"},
        ]})

    result = ReferenceGenomeService(entity_backend=_backend(handler)).resolve_entity(
        EntityResolveRequest(identifier="rs699", organism="Homo sapiens", assembly="GRCh38")
    )

    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None and result.value.entity is not None
    assert result.value.entity.start == 230_710_047
    assert result.value.entity.refs["dbSNP"] == "rs699"


def test_not_found_is_valid_empty_result() -> None:
    backend = _backend(lambda request: httpx.Response(404))
    result = ReferenceGenomeService(entity_backend=backend).resolve_entity(
        EntityResolveRequest(identifier="rs0", organism="Homo sapiens", assembly="GRCh38")
    )
    assert result.outcome is ServiceOutcome.EMPTY


def test_liftover_converts_coordinate_conventions_and_reports_unmapped() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert "1%3A101..110%3A1" in str(request.url)
            return httpx.Response(200, json={"mappings": [{"mapped": {
                "seq_region_name": "1", "start": 121, "end": 130, "strand": 1,
            }}]})
        return httpx.Response(200, json={"mappings": []})

    service = ReferenceGenomeService(liftover_backend=_backend(handler))
    result = service.liftover(LiftoverRequest(
        intervals=[
            GenomicInterval(chrom="1", start=100, end=110, assembly="GRCh37"),
            GenomicInterval(chrom="1", start=200, end=210, assembly="GRCh37"),
        ],
        source_assembly="GRCh37", target_assembly="GRCh38", organism="Homo sapiens",
    ))

    assert result.outcome is ServiceOutcome.OK
    assert result.value is not None
    assert result.value.mapped_count == 1
    assert result.value.unmapped_count == 1
    assert result.value.segments[0].target_start == 120
    assert result.evidence[0].provenance.inputs["source_assembly"] == "GRCh37"


def test_http_failure_is_recoverable_service_failure() -> None:
    backend = _backend(lambda request: httpx.Response(503, text="down"))
    result = ReferenceGenomeService(entity_backend=backend).resolve_entity(
        EntityResolveRequest(identifier="rs699", organism="Homo sapiens", assembly="GRCh38")
    )
    assert result.outcome is ServiceOutcome.FAILURE
    assert result.error is not None and result.error.kind == "BackendError"
