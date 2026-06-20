"""Annotation request/response types for the Reference Genome Service.

Large annotation outputs (whole-genome, euk gene-finding, antiSMASH, InterProScan)
MUST use object storage rather than inline JSON (RGS-4). When `storage_ref` is set in
`AnnotationResult`, the full feature set is in the object store and `features` holds
only a bounded preview.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from cellxp.domain.enums import Strand


class AnnotationFeature(BaseModel):
    """A single annotation feature (gene, CDS, regulatory region, ncRNA, BGC, …)."""

    feature_id: str
    feature_type: str  # gene, mRNA, CDS, ncRNA, regulatory_region, BGC, …
    chrom: str
    start: int  # canonical 0-based half-open
    end: int    # canonical 0-based half-open
    strand: Strand = Strand.UNSTRANDED
    name: str | None = None
    description: str | None = None
    source: str  # database or tool (e.g. "Ensembl_110", "Bakta_1.9", "antiSMASH_7")
    score: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class AnnotationRequest(BaseModel):
    """Request to annotate a genomic interval or an uploaded FASTA (de novo).

    Either `chrom`/`start`/`end` (region from a catalogued assembly) or `fasta_ref`
    (object-store key for a raw FASTA, for de novo pipelines) must be provided.
    """

    organism: str
    assembly: str
    chrom: str | None = None
    start: int | None = None  # canonical 0-based
    end: int | None = None    # canonical 0-based half-open
    fasta_ref: str | None = None  # object-store key for de novo annotation (§3)
    feature_types: list[str] = Field(default_factory=list)  # empty = all types


class AnnotationResult(BaseModel):
    """Annotation features for the requested region.

    When `storage_ref` is set, the full feature set is in object storage (RGS-4)
    and `features` contains at most a bounded preview.
    """

    organism: str
    assembly: str
    features: list[AnnotationFeature] = Field(default_factory=list)
    source_databases: list[str] = Field(default_factory=list)
    storage_ref: str | None = None
