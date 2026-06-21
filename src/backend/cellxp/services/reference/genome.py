"""Reference genome service — assembly catalog, sequence validation, entity resolution.

Implements RGS-1..RGS-5 (`specs/services/reference_genome_service.md`):
- RGS-1  coordinate-dependent callers validate here, not ad hoc.
- RGS-2  sequence extraction carries organism/assembly/contig/coord/strand/hash provenance.
- RGS-3  liftover records a provenance-bearing Step; chain-file backend is deferred.
- RGS-4  large annotation outputs use object storage; annotation backend is deferred.
- RGS-5  circular bacterial references (E. coli K-12, G. oxydans 621H) are explicit in the
          catalog; origin-crossing extraction is validated and supported.

The service separates the **catalog** (static, always available) from optional **backends**
(sequence FASTA access, liftover chain files, annotation databases) injected at runtime.
Operations that require a backend return `ServiceOutcome.UNSUPPORTED` when none is configured
rather than failing noisily — callers route on this outcome to queue the right setup step.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from cellxp.agent.state import RunError, Step
from cellxp.domain.clock import utc_now_iso
from cellxp.domain.coordinates import is_origin_crossing
from cellxp.domain.enums import (
    ConfidenceBand,
    OrganismClass,
    SourceKind,
    Strand,
    TaskStatus,
    Topology,
)
from cellxp.domain.errors import CoordinateError
from cellxp.domain.evidence import Confidence, EvidenceItem, Provenance
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.domain.validators.coordinates import validate_interval, validate_variant_position
from cellxp.services.base import Service, ServiceResult
from cellxp.services.registry import registry

from .annotations import AnnotationRequest, AnnotationResult
from .liftover import LiftoverRequest, LiftoverResult


# ---------------------------------------------------------------------------
# Catalog types
# ---------------------------------------------------------------------------


class ContigInfo(BaseModel):
    """Metadata for one contig/replicon in a reference assembly."""

    name: str
    aliases: list[str] = Field(default_factory=list)  # e.g. "1" for "chr1"
    length: int | None = None  # bp; None = not catalogued (liftover-target-only assemblies)
    topology: Topology
    is_primary: bool = True  # False for unplaced scaffolds, decoys


class AssemblyInfo(BaseModel):
    """Metadata for one reference assembly (organism × genome build)."""

    name: str  # canonical name, e.g. "GRCh38"
    organism: str
    organism_class: OrganismClass
    ucsc_name: str | None = None
    genbank_accession: str | None = None
    refseq_accession: str | None = None
    description: str | None = None
    contigs: dict[str, ContigInfo] = Field(default_factory=dict)

    def get_contig(self, name: str) -> ContigInfo | None:
        """Look up a contig by canonical name or any alias."""
        if name in self.contigs:
            return self.contigs[name]
        for contig in self.contigs.values():
            if name in contig.aliases:
                return contig
        return None


class SpeciesProfile(BaseModel):
    """Organism-level applicability contract (`supported_species.md` §3)."""

    organism: str
    organism_class: OrganismClass
    default_assembly: str
    applicable_models: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request / result types
# ---------------------------------------------------------------------------


class EntityResolveRequest(BaseModel):
    identifier: str  # gene symbol, rsID, Ensembl/RefSeq accession
    organism: str
    assembly: str | None = None
    type_hint: Literal["gene", "variant", "interval", "protein"] | None = None


class ResolvedEntity(BaseModel):
    identifier: str
    type: str  # gene, variant, interval, protein, regulatory_element
    label: str
    organism: str
    assembly: str
    chrom: str | None = None
    start: int | None = None   # canonical 0-based
    end: int | None = None     # canonical 0-based half-open
    strand: Strand | None = None
    refs: dict[str, str] = Field(default_factory=dict)  # Ensembl/RefSeq/dbSNP cross-IDs
    ambiguous: bool = False
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class EntityResolveResult(BaseModel):
    entity: ResolvedEntity | None = None
    candidates: list[ResolvedEntity] = Field(default_factory=list)


class SequenceFetchRequest(BaseModel):
    organism: str
    assembly: str
    chrom: str
    start: int   # canonical 0-based
    end: int     # canonical 0-based half-open; start >= end signals circular origin-crossing
    strand: Strand = Strand.PLUS


class SequenceFetchResult(BaseModel):
    sequence: str
    assembly: str
    chrom: str
    start: int
    end: int
    strand: Strand
    content_hash: str  # sha256(sequence.encode()) (RGS-2)
    origin_crossing: bool = False


class VariantValidationRequest(BaseModel):
    variant: Variant
    organism: str
    assembly: str
    check_ref_allele: bool = False  # requires a sequence backend


class VariantValidationResult(BaseModel):
    variant: Variant
    valid: bool
    assembly: str
    contig_length: int | None = None
    topology: Topology | None = None
    ref_allele_match: bool | None = None  # None when not checked
    fail_reason: str | None = None


class ReferenceCatalog(BaseModel):
    assemblies: list[AssemblyInfo]
    species_profiles: list[SpeciesProfile]


# ---------------------------------------------------------------------------
# Sequence backend protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class SequenceBackend(Protocol):
    """Protocol for genome-FASTA backends (local pyfaidx, remote REST, test stub).

    Implementations MUST support circular origin-crossing intervals (start >= end) for
    assemblies declared circular in the catalog (RGS-5): concatenate the suffix
    [start, contig_length) and the prefix [0, end).
    """

    def fetch(
        self,
        assembly: str,
        chrom: str,
        start: int,
        end: int,
        strand: Strand,
    ) -> str:
        """Return the DNA sequence at canonical 0-based half-open [start, end)."""
        ...


@runtime_checkable
class EntityBackend(Protocol):
    """External identifier resolver (for example Ensembl REST)."""

    name: str
    version: str

    def resolve(self, request: EntityResolveRequest, assembly: str) -> EntityResolveResult: ...


@runtime_checkable
class LiftoverBackend(Protocol):
    """Assembly-aware interval mapping backend."""

    name: str
    version: str

    def map(self, request: LiftoverRequest) -> LiftoverResult: ...


# ---------------------------------------------------------------------------
# Built-in assembly catalog
# ---------------------------------------------------------------------------


def _linear(name: str, length: int, *aliases: str) -> ContigInfo:
    return ContigInfo(name=name, length=length, topology=Topology.LINEAR, aliases=list(aliases))


def _circular(name: str, length: int | None, *aliases: str) -> ContigInfo:
    return ContigInfo(name=name, length=length, topology=Topology.CIRCULAR, aliases=list(aliases))


_GRCH38_CONTIGS: dict[str, ContigInfo] = {c.name: c for c in [
    _linear("chr1",  248_956_422, "1"),
    _linear("chr2",  242_193_529, "2"),
    _linear("chr3",  198_295_559, "3"),
    _linear("chr4",  190_214_555, "4"),
    _linear("chr5",  181_538_259, "5"),
    _linear("chr6",  170_805_979, "6"),
    _linear("chr7",  159_345_973, "7"),
    _linear("chr8",  145_138_636, "8"),
    _linear("chr9",  138_394_717, "9"),
    _linear("chr10", 133_797_422, "10"),
    _linear("chr11", 135_086_622, "11"),
    _linear("chr12", 133_275_309, "12"),
    _linear("chr13", 114_364_328, "13"),
    _linear("chr14", 107_043_718, "14"),
    _linear("chr15", 101_991_189, "15"),
    _linear("chr16",  90_338_345, "16"),
    _linear("chr17",  83_257_441, "17"),
    _linear("chr18",  80_373_285, "18"),
    _linear("chr19",  58_617_616, "19"),
    _linear("chr20",  64_444_167, "20"),
    _linear("chr21",  46_709_983, "21"),
    _linear("chr22",  50_818_468, "22"),
    _linear("chrX",  156_040_895, "X"),
    _linear("chrY",   57_227_415, "Y"),
    _circular("chrM",     16_569, "MT", "chrMT"),  # mitochondrial: circular
]}

_GRCM39_CONTIGS: dict[str, ContigInfo] = {c.name: c for c in [
    _linear("chr1",  195_154_279, "1"),
    _linear("chr2",  181_755_017, "2"),
    _linear("chr3",  159_745_466, "3"),
    _linear("chr4",  156_860_686, "4"),
    _linear("chr5",  151_758_149, "5"),
    _linear("chr6",  149_588_044, "6"),
    _linear("chr7",  144_995_196, "7"),
    _linear("chr8",  130_127_694, "8"),
    _linear("chr9",  124_359_700, "9"),
    _linear("chr10", 130_530_862, "10"),
    _linear("chr11", 121_973_369, "11"),
    _linear("chr12", 120_092_757, "12"),
    _linear("chr13", 120_883_175, "13"),
    _linear("chr14", 125_139_656, "14"),
    _linear("chr15", 104_073_951, "15"),
    _linear("chr16",  98_008_968, "16"),
    _linear("chr17",  95_294_699, "17"),
    _linear("chr18",  90_720_763, "18"),
    _linear("chr19",  61_420_004, "19"),
    _linear("chrX",  169_476_592, "X"),
    _linear("chrY",   91_455_967, "Y"),
    _circular("chrM",     16_299, "MT", "chrMT"),
]}

# E. coli K-12 MG1655 — RefSeq NC_000913.3 / GCF_000005845.2
_ECOLI_K12_CONTIGS: dict[str, ContigInfo] = {c.name: c for c in [
    _circular("NC_000913.3", 4_641_652, "chromosome", "chr"),
]}

# G. oxydans 621H — NC_006677.1 + five circular plasmids (pGOX1–5)
_GOXYDANS_CONTIGS: dict[str, ContigInfo] = {c.name: c for c in [
    _circular("NC_006677.1", 2_702_173, "chromosome", "chr"),
    _circular("NC_006671.1",   163_044, "pGOX1"),
    _circular("NC_006672.1",    26_749, "pGOX2"),
    _circular("NC_006673.1",    14_547, "pGOX3"),
    _circular("NC_006674.1",    12_896, "pGOX4"),
    _circular("NC_006675.1",     4_031, "pGOX5"),
]}

ASSEMBLY_CATALOG: dict[str, AssemblyInfo] = {
    a.name: a for a in [
        AssemblyInfo(
            name="GRCh38",
            organism="Homo sapiens",
            organism_class=OrganismClass.MAMMALIAN,
            ucsc_name="hg38",
            description="Genome Reference Consortium Human Build 38 (Dec 2013)",
            contigs=_GRCH38_CONTIGS,
        ),
        AssemblyInfo(
            name="GRCh37",
            organism="Homo sapiens",
            organism_class=OrganismClass.MAMMALIAN,
            ucsc_name="hg19",
            description="Genome Reference Consortium Human Build 37 (Feb 2009)",
            contigs={},  # contig lengths not catalogued; accepted as liftover target
        ),
        AssemblyInfo(
            name="GRCm39",
            organism="Mus musculus",
            organism_class=OrganismClass.MAMMALIAN,
            ucsc_name="mm39",
            description="Genome Reference Consortium Mouse Build 39",
            contigs=_GRCM39_CONTIGS,
        ),
        AssemblyInfo(
            name="GCF_000005845.2",
            organism="Escherichia coli",
            organism_class=OrganismClass.PROKARYOTE,
            refseq_accession="GCF_000005845.2",
            description="E. coli K-12 MG1655 (RefSeq GCF_000005845.2 / NC_000913.3)",
            contigs=_ECOLI_K12_CONTIGS,
        ),
        AssemblyInfo(
            name="GCA_000006965.1",
            organism="Gluconobacter oxydans",
            organism_class=OrganismClass.PROKARYOTE,
            refseq_accession="GCA_000006965.1",
            description="G. oxydans 621H (NC_006677.1 chromosome + pGOX1–5 plasmids)",
            contigs=_GOXYDANS_CONTIGS,
        ),
    ]
}

SPECIES_PROFILES: dict[str, SpeciesProfile] = {
    p.organism: p for p in [
        SpeciesProfile(
            organism="Homo sapiens",
            organism_class=OrganismClass.MAMMALIAN,
            default_assembly="GRCh38",
            applicable_models=["AlphaGenome", "Evo2", "SpliceAI", "ESMFold", "Boltz2"],
        ),
        SpeciesProfile(
            organism="Mus musculus",
            organism_class=OrganismClass.MAMMALIAN,
            default_assembly="GRCm39",
            applicable_models=["Evo2", "ESMFold", "Boltz2"],
        ),
        SpeciesProfile(
            organism="Escherichia coli",
            organism_class=OrganismClass.PROKARYOTE,
            default_assembly="GCF_000005845.2",
            applicable_models=["Evo2", "Bakta", "Pyrodigal", "ESMFold", "Boltz2"],
        ),
        SpeciesProfile(
            organism="Gluconobacter oxydans",
            organism_class=OrganismClass.PROKARYOTE,
            default_assembly="GCA_000006965.1",
            applicable_models=["Evo2", "Bakta", "Pyrodigal", "ESMFold", "Boltz2"],
        ),
    ]
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


@registry.register
class ReferenceGenomeService(Service):
    """Source of truth for reference assemblies and coordinate-based operations (N4).

    An optional `sequence_backend` enables `get_sequence` and ref-allele checks in
    `validate_variant`. When absent those operations return UNSUPPORTED; all catalog
    operations (list, validate bounds, resolve assembly) always work.
    """

    name = "reference_genome"

    def __init__(
        self,
        *,
        assembly_catalog: dict[str, AssemblyInfo] | None = None,
        species_profiles: dict[str, SpeciesProfile] | None = None,
        sequence_backend: SequenceBackend | None = None,
        entity_backend: EntityBackend | None = None,
        liftover_backend: LiftoverBackend | None = None,
    ) -> None:
        self._catalog = assembly_catalog if assembly_catalog is not None else ASSEMBLY_CATALOG
        self._profiles = species_profiles if species_profiles is not None else SPECIES_PROFILES
        self._seq_backend = sequence_backend
        self._entity_backend = entity_backend
        self._liftover_backend = liftover_backend

    # ------------------------------------------------------------------
    # list_supported_references
    # ------------------------------------------------------------------

    def list_supported_references(self) -> ServiceResult[ReferenceCatalog]:
        """Return the full assembly catalog and species profiles."""
        catalog = ReferenceCatalog(
            assemblies=list(self._catalog.values()),
            species_profiles=list(self._profiles.values()),
        )
        step = Step(
            name="list_supported_references",
            tool="reference_catalog",
            weight="light",
            status=TaskStatus.DONE,
            started_at=utc_now_iso(),
            finished_at=utc_now_iso(),
        )
        return ServiceResult.succeeded(
            catalog,
            steps=[step],
            evidence=[
                EvidenceItem(
                    source="reference_catalog",
                    source_kind=SourceKind.DATABASE,
                    claim=(
                        f"Catalog contains {len(catalog.assemblies)} assemblies "
                        f"and {len(catalog.species_profiles)} species profiles"
                    ),
                    confidence=Confidence(band=ConfidenceBand.HIGH),
                )
            ],
        )

    # ------------------------------------------------------------------
    # resolve_entity
    # ------------------------------------------------------------------

    def resolve_entity(
        self, request: EntityResolveRequest
    ) -> ServiceResult[EntityResolveResult]:
        """Resolve a gene symbol, rsID, or accession to a positioned entity.

        Catalog lookup (assembly existence, organism profile) runs inline. Resolution
        of gene symbols and rsIDs requires an Ensembl/dbSNP backend; those return
        UNSUPPORTED when none is configured.
        """
        started = utc_now_iso()

        # Resolve assembly from species profile when caller omits it.
        assembly = request.assembly
        if assembly is None:
            profile = self._profiles.get(request.organism)
            if profile is None:
                return ServiceResult.unsupported(
                    f"organism {request.organism!r} is not in the species catalog; "
                    f"known organisms: {', '.join(sorted(self._profiles))}",
                    steps=[_done_step("resolve_entity", started)],
                )
            assembly = profile.default_assembly

        if assembly not in self._catalog:
            return ServiceResult.unsupported(
                f"assembly {assembly!r} is not in the reference catalog; "
                f"known assemblies: {', '.join(sorted(self._catalog))}",
                steps=[_done_step("resolve_entity", started)],
            )

        if self._entity_backend is None:
            kind = "rsID/dbSNP" if request.identifier.lower().startswith("rs") else "gene/accession"
            return ServiceResult.unsupported(
                f"{kind} resolution requires an Ensembl or NCBI backend; none is configured",
                steps=[_done_step("resolve_entity", started)],
            )
        try:
            result = self._entity_backend.resolve(request, assembly)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("resolve_entity", started, error=str(exc))],
            )
        finished = utc_now_iso()
        if result.entity is None and not result.candidates:
            return ServiceResult.empty(
                f"identifier {request.identifier!r} was not found",
                steps=[_backend_step("resolve_entity", started, finished, self._entity_backend)],
            )
        return ServiceResult.succeeded(
            result,
            steps=[_backend_step("resolve_entity", started, finished, self._entity_backend)],
            evidence=[EvidenceItem(
                source=self._entity_backend.name,
                source_kind=SourceKind.DATABASE,
                claim=f"Resolved {request.identifier!r} against {assembly}",
                confidence=Confidence(band=ConfidenceBand.HIGH),
                provenance=Provenance(
                    tool=self._entity_backend.name,
                    tool_version=self._entity_backend.version,
                    inputs=request.model_dump() | {"resolved_assembly": assembly},
                    timestamp=finished,
                ),
            )],
        )

    # ------------------------------------------------------------------
    # get_sequence
    # ------------------------------------------------------------------

    def get_sequence(
        self, request: SequenceFetchRequest
    ) -> ServiceResult[SequenceFetchResult]:
        """Extract sequence at a genomic interval with full provenance (RGS-2/5).

        Validates the interval against catalog topology before hitting the backend —
        origin-crossing is accepted only for circular contigs (RGS-5).
        """
        started = utc_now_iso()

        assembly_info = self._catalog.get(request.assembly)
        if assembly_info is None:
            return ServiceResult.unsupported(
                f"assembly {request.assembly!r} is not in the reference catalog",
                steps=[_done_step("get_sequence", started)],
            )

        contig = assembly_info.get_contig(request.chrom)
        if contig is None:
            return ServiceResult.unsupported(
                f"contig {request.chrom!r} not found in {request.assembly!r}",
                steps=[_done_step("get_sequence", started)],
            )

        # Enforce topology invariants before any backend call (RGS-1/5).
        interval = GenomicInterval(
            chrom=request.chrom,
            start=request.start,
            end=request.end,
            strand=request.strand,
            assembly=request.assembly,
            species=request.organism,
        )
        try:
            validate_interval(
                interval,
                topology=contig.topology,
                contig_length=contig.length,
            )
        except CoordinateError as exc:
            return ServiceResult.failed(
                RunError(kind="CoordinateError", message=str(exc)),
                steps=[_failed_step("get_sequence", started, error=str(exc))],
            )

        if self._seq_backend is None:
            return ServiceResult.unsupported(
                "sequence extraction requires a genome FASTA backend; none is configured",
                steps=[_done_step("get_sequence", started)],
            )

        try:
            seq = self._seq_backend.fetch(
                request.assembly,
                request.chrom,
                request.start,
                request.end,
                request.strand,
            )
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("get_sequence", started, error=str(exc))],
            )

        content_hash = hashlib.sha256(seq.encode()).hexdigest()
        origin_crossing = is_origin_crossing(request.start, request.end)
        finished = utc_now_iso()

        return ServiceResult.succeeded(
            SequenceFetchResult(
                sequence=seq,
                assembly=request.assembly,
                chrom=request.chrom,
                start=request.start,
                end=request.end,
                strand=request.strand,
                content_hash=content_hash,
                origin_crossing=origin_crossing,
            ),
            steps=[
                Step(
                    name="get_sequence",
                    tool="sequence_backend",
                    tool_version="unknown",
                    weight="light",
                    status=TaskStatus.DONE,
                    started_at=started,
                    finished_at=finished,
                )
            ],
            evidence=[
                EvidenceItem(
                    source=request.assembly,
                    source_kind=SourceKind.DATABASE,
                    claim=(
                        f"Sequence extracted from {request.chrom}:"
                        f"{request.start}-{request.end} ({request.strand.value})"
                    ),
                    confidence=Confidence(band=ConfidenceBand.HIGH),
                    provenance=Provenance(
                        tool="sequence_backend",
                        tool_version="unknown",
                        inputs={
                            "organism": request.organism,
                            "assembly": request.assembly,
                            "chrom": request.chrom,
                            "start": request.start,
                            "end": request.end,
                            "strand": request.strand.value,
                        },
                        output_hash=content_hash,
                        timestamp=finished,
                    ),
                )
            ],
        )

    # ------------------------------------------------------------------
    # validate_variant
    # ------------------------------------------------------------------

    def validate_variant(
        self, request: VariantValidationRequest
    ) -> ServiceResult[VariantValidationResult]:
        """Validate a variant's position against the reference catalog (RGS-1).

        Returns a succeeded result whose `valid` field indicates whether the variant is
        in-bounds for its contig. An unknown assembly or contig returns UNSUPPORTED rather
        than a validation failure so callers can distinguish missing data from bad data.
        """
        started = utc_now_iso()

        assembly_info = self._catalog.get(request.assembly)
        if assembly_info is None:
            return ServiceResult.unsupported(
                f"assembly {request.assembly!r} is not in the reference catalog; "
                f"known assemblies: {', '.join(sorted(self._catalog))}",
                steps=[_done_step("validate_variant", started)],
            )

        contig = assembly_info.get_contig(request.variant.chrom)
        if contig is None:
            return ServiceResult.succeeded(
                VariantValidationResult(
                    variant=request.variant,
                    valid=False,
                    assembly=request.assembly,
                    fail_reason=(
                        f"contig {request.variant.chrom!r} not found in {request.assembly!r}"
                    ),
                ),
                steps=[_done_step("validate_variant", started)],
            )

        try:
            validate_variant_position(request.variant, contig_length=contig.length)
        except CoordinateError as exc:
            return ServiceResult.succeeded(
                VariantValidationResult(
                    variant=request.variant,
                    valid=False,
                    assembly=request.assembly,
                    contig_length=contig.length,
                    topology=contig.topology,
                    fail_reason=str(exc),
                ),
                steps=[_done_step("validate_variant", started)],
            )

        # Optional ref-allele check (requires sequence backend).
        ref_allele_match: bool | None = None
        if request.check_ref_allele:
            if self._seq_backend is None:
                return ServiceResult.unsupported(
                    "ref-allele check requires a sequence backend; none is configured",
                    steps=[_done_step("validate_variant", started)],
                )
            try:
                ref_seq = self._seq_backend.fetch(
                    request.assembly,
                    request.variant.chrom,
                    request.variant.pos,
                    request.variant.pos + len(request.variant.ref),
                    Strand.PLUS,
                )
                ref_allele_match = ref_seq.upper() == request.variant.ref.upper()
            except Exception as exc:  # noqa: BLE001
                return ServiceResult.failed(
                    RunError(kind="BackendError", message=str(exc)),
                    steps=[_failed_step("validate_variant", started, error=str(exc))],
                )

        return ServiceResult.succeeded(
            VariantValidationResult(
                variant=request.variant,
                valid=True,
                assembly=request.assembly,
                contig_length=contig.length,
                topology=contig.topology,
                ref_allele_match=ref_allele_match,
            ),
            steps=[_done_step("validate_variant", started)],
            evidence=[
                EvidenceItem(
                    source="reference_catalog",
                    source_kind=SourceKind.COMPUTATION,
                    claim=(
                        f"Variant {request.variant.chrom}:{request.variant.pos} is "
                        f"in-bounds for {request.assembly}"
                    ),
                    confidence=Confidence(band=ConfidenceBand.HIGH),
                    provenance=Provenance(
                        tool="reference_catalog",
                        inputs={
                            "assembly": request.assembly,
                            "chrom": request.variant.chrom,
                        },
                    ),
                )
            ],
        )

    # ------------------------------------------------------------------
    # liftover
    # ------------------------------------------------------------------

    def liftover(self, request: LiftoverRequest) -> ServiceResult[LiftoverResult]:
        """Lift genomic intervals between assemblies (RGS-3).

        Both source and target assemblies must be in the catalog. The actual coordinate
        remapping requires a chain-file backend (CrossMap); that step returns UNSUPPORTED
        until one is configured.
        """
        started = utc_now_iso()

        for asm in (request.source_assembly, request.target_assembly):
            if asm not in self._catalog:
                return ServiceResult.unsupported(
                    f"assembly {asm!r} is not in the reference catalog; liftover requires "
                    f"both source and target to be catalogued",
                    steps=[_done_step("liftover", started)],
                )

        if self._liftover_backend is None:
            return ServiceResult.unsupported(
                f"liftover from {request.source_assembly!r} to {request.target_assembly!r} "
                f"requires an Ensembl or chain-file mapping backend; none is configured",
                steps=[_done_step("liftover", started)],
            )
        try:
            result = self._liftover_backend.map(request)
        except Exception as exc:  # noqa: BLE001
            return ServiceResult.failed(
                RunError(kind="BackendError", message=str(exc)),
                steps=[_failed_step("liftover", started, error=str(exc))],
            )
        finished = utc_now_iso()
        return ServiceResult.succeeded(
            result,
            steps=[_backend_step("liftover", started, finished, self._liftover_backend)],
            evidence=[EvidenceItem(
                source=self._liftover_backend.name,
                source_kind=SourceKind.DATABASE,
                claim=(f"Mapped {result.mapped_count}/{len(result.segments)} segments from "
                       f"{request.source_assembly} to {request.target_assembly}"),
                confidence=Confidence(band=ConfidenceBand.HIGH),
                provenance=Provenance(
                    tool=self._liftover_backend.name,
                    tool_version=self._liftover_backend.version,
                    inputs={
                        "organism": request.organism,
                        "source_assembly": request.source_assembly,
                        "target_assembly": request.target_assembly,
                        "intervals": [item.model_dump() for item in request.intervals],
                    },
                    timestamp=finished,
                ),
            )],
        )

    # ------------------------------------------------------------------
    # annotate
    # ------------------------------------------------------------------

    def annotate(self, request: AnnotationRequest) -> ServiceResult[AnnotationResult]:
        """Annotate a genomic region or FASTA with gene models and functional features.

        Requires an annotation database backend (Ensembl REST, Bakta, Helixer, antiSMASH).
        Large outputs would be stored via object storage (RGS-4); both are deferred to
        the annotation backend, returning UNSUPPORTED until one is configured.
        """
        started = utc_now_iso()

        if request.assembly not in self._catalog:
            return ServiceResult.unsupported(
                f"assembly {request.assembly!r} is not in the reference catalog",
                steps=[_done_step("annotate", started)],
            )

        return ServiceResult.unsupported(
            "annotation requires a database backend (Ensembl, Bakta, Helixer, antiSMASH); "
            "none is configured",
            steps=[_done_step("annotate", started)],
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _done_step(name: str, started: str) -> Step:
    return Step(
        name=name,
        tool="reference_catalog",
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=utc_now_iso(),
    )


def _failed_step(name: str, started: str, *, error: str) -> Step:
    return Step(
        name=name,
        tool="reference_catalog",
        weight="light",
        status=TaskStatus.FAILED,
        started_at=started,
        finished_at=utc_now_iso(),
        error=error,
    )


def _backend_step(name: str, started: str, finished: str, backend: Any) -> Step:
    return Step(
        name=name,
        tool=backend.name,
        tool_version=backend.version,
        weight="light",
        status=TaskStatus.DONE,
        started_at=started,
        finished_at=finished,
    )
