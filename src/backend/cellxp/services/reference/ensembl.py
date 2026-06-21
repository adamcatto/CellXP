"""Production Ensembl REST adapters for entity resolution and assembly mapping."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from cellxp.domain.enums import Strand

from .genome import EntityResolveRequest, EntityResolveResult, ResolvedEntity
from .liftover import LiftoverRequest, LiftoverResult, LiftoverSegment


class EnsemblRestBackend:
    """Resolve Ensembl/dbSNP identifiers and lift intervals through Ensembl REST.

    The client is injectable for deterministic tests and deployments that need custom
    TLS, proxies, authentication, or retry transports.
    """

    name = "ensembl_rest"

    def __init__(
        self,
        *,
        base_url: str = "https://rest.ensembl.org",
        timeout: float = 20.0,
        version: str = "rest-v1",
        client: httpx.Client | None = None,
    ) -> None:
        self.version = version
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def resolve(self, request: EntityResolveRequest, assembly: str) -> EntityResolveResult:
        if request.identifier.lower().startswith("rs"):
            entities = self._resolve_variant(request, assembly)
        else:
            entities = self._resolve_feature(request, assembly)
        if len(entities) == 1:
            return EntityResolveResult(entity=entities[0])
        if len(entities) > 1:
            entities = [item.model_copy(update={"ambiguous": True}) for item in entities]
        return EntityResolveResult(candidates=entities)

    def _resolve_variant(
        self, request: EntityResolveRequest, assembly: str
    ) -> list[ResolvedEntity]:
        species = _species_slug(request.organism)
        payload = self._get_json(f"/variation/{quote(species)}/{quote(request.identifier)}")
        if not isinstance(payload, dict):
            return []
        entities: list[ResolvedEntity] = []
        for mapping in payload.get("mappings", []):
            if mapping.get("assembly_name") != assembly:
                continue
            start = int(mapping["start"]) - 1
            end = int(mapping["end"])
            chrom = str(mapping["seq_region_name"])
            alleles = str(mapping.get("allele_string", ""))
            entities.append(ResolvedEntity(
                identifier=request.identifier,
                type="variant",
                label=request.identifier,
                organism=request.organism,
                assembly=assembly,
                chrom=chrom,
                start=start,
                end=end,
                strand=_strand(mapping.get("strand")),
                refs={"dbSNP": request.identifier, "alleles": alleles},
            ))
        return entities

    def _resolve_feature(
        self, request: EntityResolveRequest, assembly: str
    ) -> list[ResolvedEntity]:
        identifier = quote(request.identifier)
        if request.identifier.upper().startswith(("ENS", "LRG_")):
            records = [self._get_json(f"/lookup/id/{identifier}?expand=0")]
        else:
            species = _species_slug(request.organism)
            xrefs = self._get_json(f"/xrefs/symbol/{quote(species)}/{identifier}")
            records = [self._get_json(f"/lookup/id/{quote(str(x['id']))}?expand=0") for x in xrefs]
        entities = []
        seen: set[str] = set()
        for record in records:
            stable_id = str(record.get("id", request.identifier))
            if stable_id in seen or record.get("assembly_name") not in (None, assembly):
                continue
            seen.add(stable_id)
            feature_type = str(record.get("object_type", "gene")).lower()
            entities.append(ResolvedEntity(
                identifier=stable_id,
                type=feature_type,
                label=str(record.get("display_name") or request.identifier),
                organism=request.organism,
                assembly=assembly,
                chrom=str(record["seq_region_name"]) if record.get("seq_region_name") else None,
                start=int(record["start"]) - 1 if record.get("start") is not None else None,
                end=int(record["end"]) if record.get("end") is not None else None,
                strand=_strand(record.get("strand")),
                refs={"Ensembl": stable_id},
            ))
        return entities

    def map(self, request: LiftoverRequest) -> LiftoverResult:
        species = _species_slug(request.organism)
        segments: list[LiftoverSegment] = []
        for interval in request.intervals:
            # Ensembl regions are 1-based inclusive; internal intervals are 0-based half-open.
            region = f"{interval.chrom}:{interval.start + 1}..{interval.end}:1"
            path = (f"/map/{quote(species)}/{quote(request.source_assembly)}/"
                    f"{quote(region)}/{quote(request.target_assembly)}")
            payload = self._get_json(path)
            mappings = payload.get("mappings", [])
            if not mappings:
                segments.append(_unmapped(interval.chrom, interval.start, interval.end))
                continue
            for item in mappings:
                mapped = item.get("mapped", {})
                if not mapped:
                    segments.append(_unmapped(interval.chrom, interval.start, interval.end))
                    continue
                segments.append(LiftoverSegment(
                    source_chrom=interval.chrom,
                    source_start=interval.start,
                    source_end=interval.end,
                    target_chrom=str(mapped["seq_region_name"]),
                    target_start=int(mapped["start"]) - 1,
                    target_end=int(mapped["end"]),
                    mapped=True,
                ))
        mapped_count = sum(segment.mapped for segment in segments)
        return LiftoverResult(
            source_assembly=request.source_assembly,
            target_assembly=request.target_assembly,
            organism=request.organism,
            segments=segments,
            mapped_count=mapped_count,
            unmapped_count=len(segments) - mapped_count,
        )

    def _get_json(self, path: str) -> Any:
        response = self._client.get(path)
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json()


def _species_slug(organism: str) -> str:
    return organism.strip().lower().replace(" ", "_")


def _strand(value: Any) -> Strand | None:
    if value in (1, "1"):
        return Strand.PLUS
    if value in (-1, "-1"):
        return Strand.MINUS
    return None


def _unmapped(chrom: str, start: int, end: int) -> LiftoverSegment:
    return LiftoverSegment(
        source_chrom=chrom,
        source_start=start,
        source_end=end,
        mapped=False,
        fail_reason="Ensembl returned no mapping",
    )
