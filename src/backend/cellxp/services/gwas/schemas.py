"""Typed requests, results, and backend protocol for GWAS/QTL analysis."""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval, Variant


class GeneReference(BaseModel):
    """A gene identifier resolved against an explicit organism and assembly."""

    identifier: str


class Association(BaseModel):
    trait: str
    variant_id: str | None = None
    beta: float | None = None
    p_value: float | None = Field(default=None, ge=0.0, le=1.0)
    association_score: float | None = Field(default=None, ge=0.0, le=1.0)
    effect_allele: str | None = None
    study_accession: str
    citations: list[str] = Field(min_length=1)
    source: str
    source_release: str
    sample_size: int | None = None


class CredibleVariant(BaseModel):
    variant_id: str
    pip: float = Field(ge=0.0, le=1.0)


class CredibleSet(BaseModel):
    id: str
    variants: list[CredibleVariant]
    region: GenomicInterval
    coverage: float = Field(ge=0.0, le=1.0)


class LdPair(BaseModel):
    variant_a: str
    variant_b: str
    r2: float = Field(ge=0.0, le=1.0)


class ColocResult(BaseModel):
    trait: str
    tissue: str
    h4: float = Field(ge=0.0, le=1.0)
    gwas_dataset: str
    qtl_dataset: str


class GwasRequest(BaseModel):
    subject: Variant | GenomicInterval | GeneReference
    organism: str
    assembly: str
    traits: list[str] | None = None
    tissues: list[str] | None = None
    ld_population: str | None = None
    source_release: str = "default"
    do_finemap: bool = True
    do_coloc: bool = True


class GwasResult(BaseModel):
    associations: list[Association] = Field(default_factory=list)
    credible_sets: list[CredibleSet] = Field(default_factory=list)
    coloc: list[ColocResult] = Field(default_factory=list)
    ld: list[LdPair] | None = None
    confidence: Confidence
    provenance: Provenance = Field(default_factory=Provenance)
    storage_ref: str | None = None
    locus_plot_ref: str | None = None
    coverage_note: str | None = None


class LdRequest(BaseModel):
    interval: GenomicInterval
    organism: str
    assembly: str
    population: str
    lead_variants: list[str] = Field(default_factory=list)
    source_release: str = "default"


class LdResult(BaseModel):
    pairs: list[LdPair] = Field(default_factory=list)
    population: str
    panel: str
    assumptions: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    storage_ref: str | None = None
    locus_plot_ref: str | None = None


class FineMapRequest(BaseModel):
    interval: GenomicInterval
    organism: str
    assembly: str
    trait: str
    population: str | None = None
    summary_stats_ref: str
    ld_matrix_ref: str | None = None
    source_release: str = "default"
    method: Literal["susie"] = "susie"


class FineMapResult(BaseModel):
    credible_sets: list[CredibleSet] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    input_datasets: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    storage_ref: str | None = None
    locus_plot_ref: str | None = None


class ColocRequest(BaseModel):
    interval: GenomicInterval
    organism: str
    assembly: str
    trait: str
    tissues: list[str]
    gwas_stats_ref: str
    qtl_stats_ref: str
    source_release: str = "default"
    method: Literal["coloc"] = "coloc"


class ColocBatchResult(BaseModel):
    results: list[ColocResult] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    input_datasets: list[str] = Field(default_factory=list)
    provenance: Provenance = Field(default_factory=Provenance)
    storage_ref: str | None = None
    locus_plot_ref: str | None = None


@runtime_checkable
class GwasBackend(Protocol):
    """Injectable adapter for catalog, LD, SuSiE, and coloc implementations."""

    def lookup_associations(self, request: GwasRequest) -> GwasResult: ...

    def compute_ld(self, request: LdRequest) -> LdResult: ...

    def fine_map(self, request: FineMapRequest) -> FineMapResult: ...

    def coloc(self, request: ColocRequest) -> ColocBatchResult: ...
