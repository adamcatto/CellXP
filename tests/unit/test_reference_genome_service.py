"""Unit tests for the N4 Reference Genome Service (RGS-1..RGS-5).

Coverage:
- Assembly catalog content: GRCh38, GRCm39, E. coli K-12, G. oxydans 621H.
- ContigInfo alias resolution.
- Circular topology: origin-crossing interval accepted on circular, rejected on linear.
- validate_variant: in-bounds, out-of-bounds, unknown assembly/contig, ref-allele check.
- get_sequence: topology guard, in-memory backend, no-backend path, provenance (RGS-2).
- resolve_entity: unknown organism/assembly → UNSUPPORTED; rsID/gene-symbol stubs.
- liftover: unknown assembly → UNSUPPORTED; both known → UNSUPPORTED (no chain file).
- annotate: unknown assembly → UNSUPPORTED; known → UNSUPPORTED (no backend).
- Every succeeded result carries at least one Step (PROV-1).
"""

from __future__ import annotations

from cellxp.domain.enums import OrganismClass, Strand, TaskStatus, Topology
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.services.base import ServiceOutcome
from cellxp.services.reference.annotations import AnnotationRequest
from cellxp.services.reference.genome import (
    ASSEMBLY_CATALOG,
    SPECIES_PROFILES,
    AssemblyInfo,
    ContigInfo,
    EntityResolveRequest,
    ReferenceGenomeService,
    SequenceFetchRequest,
    SpeciesProfile,
    VariantValidationRequest,
)
from cellxp.services.reference.liftover import LiftoverRequest

# ---------------------------------------------------------------------------
# Test double: in-memory sequence backend
# ---------------------------------------------------------------------------


class _InMemoryBackend:
    """Minimal SequenceBackend stub for unit tests.

    Stores full contig sequences keyed by (assembly, chrom). Supports circular
    origin-crossing (start >= end) by concatenating suffix + prefix (RGS-5).
    """

    def __init__(self, sequences: dict[tuple[str, str], str]) -> None:
        self._seqs = sequences

    def fetch(self, assembly: str, chrom: str, start: int, end: int, strand: Strand) -> str:
        key = (assembly, chrom)
        if key not in self._seqs:
            raise RuntimeError(f"no test sequence for {assembly}/{chrom}")
        full = self._seqs[key]
        if start >= end:  # circular origin-crossing
            return full[start:] + full[:end]
        return full[start:end]


def _service(**kwargs) -> ReferenceGenomeService:
    """Create a service using the global catalog (keyword args forwarded to __init__)."""
    return ReferenceGenomeService(**kwargs)


# ---------------------------------------------------------------------------
# Catalog content
# ---------------------------------------------------------------------------


class TestAssemblyCatalog:
    def test_grch38_present(self):
        assert "GRCh38" in ASSEMBLY_CATALOG

    def test_grcm39_present(self):
        assert "GRCm39" in ASSEMBLY_CATALOG

    def test_ecoli_k12_present(self):
        assert "GCF_000005845.2" in ASSEMBLY_CATALOG

    def test_goxydans_present(self):
        assert "GCA_000006965.1" in ASSEMBLY_CATALOG

    def test_grch38_organism_class_is_mammalian(self):
        assert ASSEMBLY_CATALOG["GRCh38"].organism_class is OrganismClass.MAMMALIAN

    def test_ecoli_organism_class_is_prokaryote(self):
        assert ASSEMBLY_CATALOG["GCF_000005845.2"].organism_class is OrganismClass.PROKARYOTE

    def test_goxydans_organism_class_is_prokaryote(self):
        assert ASSEMBLY_CATALOG["GCA_000006965.1"].organism_class is OrganismClass.PROKARYOTE

    def test_grch38_has_autosomes_and_sex_chromosomes(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        for chrom in ("chr1", "chrX", "chrY"):
            assert asm.get_contig(chrom) is not None

    def test_grch38_chrom_lengths_are_positive(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        for contig in asm.contigs.values():
            assert contig.length is not None and contig.length > 0

    def test_grch38_mitochondrial_is_circular(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        mt = asm.get_contig("chrM")
        assert mt is not None
        assert mt.topology is Topology.CIRCULAR

    def test_grch38_autosomes_are_linear(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        assert asm.get_contig("chr1").topology is Topology.LINEAR

    def test_ecoli_chromosome_is_circular(self):
        asm = ASSEMBLY_CATALOG["GCF_000005845.2"]
        chrom = asm.get_contig("NC_000913.3")
        assert chrom is not None
        assert chrom.topology is Topology.CIRCULAR

    def test_goxydans_chromosome_is_circular(self):
        asm = ASSEMBLY_CATALOG["GCA_000006965.1"]
        chrom = asm.get_contig("NC_006677.1")
        assert chrom is not None
        assert chrom.topology is Topology.CIRCULAR

    def test_goxydans_has_plasmids(self):
        asm = ASSEMBLY_CATALOG["GCA_000006965.1"]
        for replicon in ("NC_006671.1", "NC_006672.1", "NC_006673.1"):
            assert asm.get_contig(replicon) is not None

    def test_goxydans_plasmids_are_circular(self):
        asm = ASSEMBLY_CATALOG["GCA_000006965.1"]
        for replicon in ("NC_006671.1", "NC_006672.1"):
            assert asm.get_contig(replicon).topology is Topology.CIRCULAR


class TestContigAliasResolution:
    def test_numeric_alias_resolves_grch38_chr1(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        assert asm.get_contig("1") is asm.get_contig("chr1")

    def test_mt_alias_resolves_grch38_chrm(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        assert asm.get_contig("MT") is asm.get_contig("chrM")

    def test_chromosome_alias_resolves_ecoli_contig(self):
        asm = ASSEMBLY_CATALOG["GCF_000005845.2"]
        assert asm.get_contig("chromosome") is asm.get_contig("NC_000913.3")

    def test_unknown_contig_returns_none(self):
        asm = ASSEMBLY_CATALOG["GRCh38"]
        assert asm.get_contig("chrUNKNOWN") is None


class TestSpeciesProfiles:
    def test_homo_sapiens_default_assembly_is_grch38(self):
        assert SPECIES_PROFILES["Homo sapiens"].default_assembly == "GRCh38"

    def test_ecoli_default_assembly_matches_catalog(self):
        profile = SPECIES_PROFILES["Escherichia coli"]
        assert profile.default_assembly in ASSEMBLY_CATALOG

    def test_prokaryote_profiles_include_evo2(self):
        for organism in ("Escherichia coli", "Gluconobacter oxydans"):
            assert "Evo2" in SPECIES_PROFILES[organism].applicable_models


# ---------------------------------------------------------------------------
# list_supported_references
# ---------------------------------------------------------------------------


class TestListSupportedReferences:
    def test_returns_ok(self):
        svc = _service()
        result = svc.list_supported_references()
        assert result.outcome is ServiceOutcome.OK

    def test_catalog_contains_all_assemblies(self):
        svc = _service()
        result = svc.list_supported_references()
        names = {a.name for a in result.value.assemblies}
        assert {"GRCh38", "GRCm39", "GCF_000005845.2", "GCA_000006965.1"}.issubset(names)

    def test_species_profiles_present(self):
        svc = _service()
        result = svc.list_supported_references()
        organisms = {p.organism for p in result.value.species_profiles}
        assert "Homo sapiens" in organisms
        assert "Escherichia coli" in organisms

    def test_result_has_at_least_one_step(self):
        svc = _service()
        result = svc.list_supported_references()
        assert len(result.steps) >= 1

    def test_step_is_done(self):
        svc = _service()
        result = svc.list_supported_references()
        assert all(s.status is TaskStatus.DONE for s in result.steps)


# ---------------------------------------------------------------------------
# validate_variant
# ---------------------------------------------------------------------------


class TestValidateVariant:
    def _req(self, chrom: str, pos: int, assembly: str = "GRCh38") -> VariantValidationRequest:
        return VariantValidationRequest(
            variant=Variant(chrom=chrom, pos=pos, ref="A", alt="T", assembly=assembly),
            organism="Homo sapiens",
            assembly=assembly,
        )

    def test_valid_variant_on_grch38(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 1000))
        assert result.outcome is ServiceOutcome.OK
        assert result.value.valid is True

    def test_valid_variant_returns_contig_length(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 1000))
        assert result.value.contig_length == 248_956_422

    def test_valid_variant_returns_topology(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 1000))
        assert result.value.topology is Topology.LINEAR

    def test_out_of_bounds_variant_is_invalid(self):
        svc = _service()
        # chr22 length is 50_818_468; pos beyond that
        result = svc.validate_variant(self._req("chr22", 60_000_000))
        assert result.outcome is ServiceOutcome.OK
        assert result.value.valid is False
        assert result.value.fail_reason is not None

    def test_unknown_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 0, assembly="UnknownAsm"))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_contig_returns_invalid(self):
        svc = _service()
        result = svc.validate_variant(self._req("chrUNKNOWN", 0))
        assert result.outcome is ServiceOutcome.OK
        assert result.value.valid is False

    def test_valid_variant_carries_step(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 1000))
        assert len(result.steps) >= 1

    def test_valid_variant_carries_evidence(self):
        svc = _service()
        result = svc.validate_variant(self._req("chr1", 1000))
        assert len(result.evidence) >= 1

    def test_check_ref_allele_without_backend_returns_unsupported(self):
        svc = _service()
        req = VariantValidationRequest(
            variant=Variant(chrom="chr1", pos=100, ref="A", alt="T"),
            organism="Homo sapiens",
            assembly="GRCh38",
            check_ref_allele=True,
        )
        result = svc.validate_variant(req)
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_check_ref_allele_with_matching_backend(self):
        seq = "A" * 200  # all A's at positions 0..199
        backend = _InMemoryBackend({("GRCh38", "chr1"): seq * 1_000_000})
        svc = _service(sequence_backend=backend)
        req = VariantValidationRequest(
            variant=Variant(chrom="chr1", pos=50, ref="A", alt="T"),
            organism="Homo sapiens",
            assembly="GRCh38",
            check_ref_allele=True,
        )
        result = svc.validate_variant(req)
        assert result.outcome is ServiceOutcome.OK
        assert result.value.ref_allele_match is True

    def test_prokaryote_variant_in_bounds(self):
        svc = _service()
        req = VariantValidationRequest(
            variant=Variant(chrom="NC_000913.3", pos=1_000_000, ref="G", alt="C",
                            assembly="GCF_000005845.2"),
            organism="Escherichia coli",
            assembly="GCF_000005845.2",
        )
        result = svc.validate_variant(req)
        assert result.outcome is ServiceOutcome.OK
        assert result.value.valid is True
        assert result.value.topology is Topology.CIRCULAR

    def test_prokaryote_variant_alias_resolution(self):
        svc = _service()
        req = VariantValidationRequest(
            # "chromosome" is an alias for NC_000913.3
            variant=Variant(chrom="chromosome", pos=500_000, ref="G", alt="A",
                            assembly="GCF_000005845.2"),
            organism="Escherichia coli",
            assembly="GCF_000005845.2",
        )
        result = svc.validate_variant(req)
        assert result.outcome is ServiceOutcome.OK
        assert result.value.valid is True


# ---------------------------------------------------------------------------
# get_sequence
# ---------------------------------------------------------------------------


class TestGetSequence:
    def _req(
        self, chrom: str, start: int, end: int,
        assembly: str = "GRCh38",
        organism: str = "Homo sapiens",
        strand: Strand = Strand.PLUS,
    ) -> SequenceFetchRequest:
        return SequenceFetchRequest(
            organism=organism, assembly=assembly, chrom=chrom,
            start=start, end=end, strand=strand,
        )

    def test_no_backend_returns_unsupported(self):
        svc = _service()
        result = svc.get_sequence(self._req("chr1", 0, 100))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.get_sequence(self._req("chr1", 0, 100, assembly="Fake"))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_contig_returns_unsupported(self):
        svc = _service()
        result = svc.get_sequence(self._req("chrZ", 0, 100))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_linear_contig_rejects_origin_crossing(self):
        svc = _service()
        # start > end on a linear chromosome is a CoordinateError, not just unsupported
        result = svc.get_sequence(self._req("chr1", 200, 100))
        assert result.outcome is ServiceOutcome.FAILURE

    def test_circular_contig_accepts_origin_crossing(self):
        # E. coli chromosome NC_000913.3 is circular — origin-crossing must be accepted.
        contig_len = ASSEMBLY_CATALOG["GCF_000005845.2"].get_contig("NC_000913.3").length
        raw_seq = ("ACGT" * (contig_len // 4 + 1))[:contig_len]
        backend = _InMemoryBackend({("GCF_000005845.2", "NC_000913.3"): raw_seq})
        svc = _service(sequence_backend=backend)
        # span across the origin: start near end of chromosome, end near start
        result = svc.get_sequence(self._req(
            "NC_000913.3",
            contig_len - 10, 10,  # origin-crossing (start >= end)
            assembly="GCF_000005845.2",
            organism="Escherichia coli",
        ))
        assert result.outcome is ServiceOutcome.OK
        assert result.value.origin_crossing is True
        assert len(result.value.sequence) == 20  # (contig_len-10)..(contig_len) + 0..10

    def test_sequence_extraction_returns_content_hash(self):
        import hashlib
        seq_data = "ACGT" * 50
        backend = _InMemoryBackend({("GRCh38", "chr1"): seq_data * 10_000_000})
        svc = _service(sequence_backend=backend)
        result = svc.get_sequence(self._req("chr1", 0, 8))
        assert result.outcome is ServiceOutcome.OK
        expected_hash = hashlib.sha256(b"ACGTACGT").hexdigest()
        assert result.value.content_hash == expected_hash

    def test_sequence_extraction_provenance_rgs2(self):
        seq_data = "AAAA" * 1_000_000
        backend = _InMemoryBackend({("GRCh38", "chr1"): seq_data})
        svc = _service(sequence_backend=backend)
        result = svc.get_sequence(self._req("chr1", 0, 100))
        assert result.outcome is ServiceOutcome.OK
        # RGS-2: provenance must record organism, assembly, chrom, coords, strand.
        assert len(result.evidence) >= 1
        prov = result.evidence[0].provenance
        assert prov.inputs.get("organism") == "Homo sapiens"
        assert prov.inputs.get("assembly") == "GRCh38"
        assert prov.inputs.get("chrom") == "chr1"
        assert prov.output_hash is not None

    def test_sequence_extraction_step_is_done(self):
        seq_data = "GCGC" * 1_000_000
        backend = _InMemoryBackend({("GRCh38", "chr1"): seq_data})
        svc = _service(sequence_backend=backend)
        result = svc.get_sequence(self._req("chr1", 0, 50))
        assert all(s.status is TaskStatus.DONE for s in result.steps)

    def test_mitochondrial_circular_linear_boundary(self):
        # chrM is circular (16,569 bp) — origin-crossing is valid.
        contig_len = ASSEMBLY_CATALOG["GRCh38"].get_contig("chrM").length
        backend = _InMemoryBackend({
            ("GRCh38", "chrM"): "N" * contig_len
        })
        svc = _service(sequence_backend=backend)
        result = svc.get_sequence(self._req("chrM", contig_len - 5, 5))
        assert result.outcome is ServiceOutcome.OK
        assert result.value.origin_crossing is True


# ---------------------------------------------------------------------------
# resolve_entity
# ---------------------------------------------------------------------------


class TestResolveEntity:
    def test_unknown_organism_returns_unsupported(self):
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="BRCA1", organism="Martian"
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="BRCA1", organism="Homo sapiens", assembly="FakeAsm"
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_rsid_without_backend_returns_unsupported(self):
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="rs334", organism="Homo sapiens"
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_gene_symbol_without_backend_returns_unsupported(self):
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="BRCA1", organism="Homo sapiens"
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_omitted_assembly_resolves_to_species_default(self):
        # Not an error even without explicit assembly — we just need the organism profile.
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="TP53", organism="Homo sapiens"
        ))
        # Returns UNSUPPORTED (no backend), not a catalog error — assembly resolved correctly.
        assert result.outcome is ServiceOutcome.UNSUPPORTED
        assert "Ensembl" in result.detail or "NCBI" in result.detail

    def test_resolve_entity_result_carries_step(self):
        svc = _service()
        result = svc.resolve_entity(EntityResolveRequest(
            identifier="BRCA1", organism="Homo sapiens"
        ))
        assert len(result.steps) >= 1


# ---------------------------------------------------------------------------
# liftover (RGS-3)
# ---------------------------------------------------------------------------


class TestLiftover:
    def _req(self, src: str, tgt: str, organism: str = "Homo sapiens") -> LiftoverRequest:
        return LiftoverRequest(
            intervals=[GenomicInterval(chrom="chr1", start=1000, end=2000, assembly=src)],
            source_assembly=src,
            target_assembly=tgt,
            organism=organism,
        )

    def test_unknown_source_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.liftover(self._req("FakeAsm", "GRCh37"))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_target_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.liftover(self._req("GRCh38", "FakeAsm"))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_both_known_assemblies_returns_unsupported_no_chain_file(self):
        svc = _service()
        result = svc.liftover(self._req("GRCh38", "GRCh37"))
        assert result.outcome is ServiceOutcome.UNSUPPORTED
        assert "chain" in result.detail.lower() or "CrossMap" in result.detail

    def test_liftover_carries_step(self):
        svc = _service()
        result = svc.liftover(self._req("GRCh38", "GRCh37"))
        assert len(result.steps) >= 1


# ---------------------------------------------------------------------------
# annotate (RGS-4)
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_unknown_assembly_returns_unsupported(self):
        svc = _service()
        result = svc.annotate(AnnotationRequest(
            organism="Homo sapiens", assembly="FakeAsm", chrom="chr1", start=0, end=50000
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_known_assembly_returns_unsupported_no_backend(self):
        svc = _service()
        result = svc.annotate(AnnotationRequest(
            organism="Homo sapiens", assembly="GRCh38", chrom="chr1", start=0, end=50000
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_annotate_carries_step(self):
        svc = _service()
        result = svc.annotate(AnnotationRequest(
            organism="Escherichia coli", assembly="GCF_000005845.2"
        ))
        assert len(result.steps) >= 1


# ---------------------------------------------------------------------------
# Cross-cutting: steps (PROV-1) on all operations
# ---------------------------------------------------------------------------


class TestProvenanceSteps:
    """Every operation — success or unsupported — must return at least one Step."""

    def _svc(self) -> ReferenceGenomeService:
        return _service()

    def test_list_has_steps(self):
        assert len(self._svc().list_supported_references().steps) >= 1

    def test_validate_variant_has_steps(self):
        svc = self._svc()
        result = svc.validate_variant(VariantValidationRequest(
            variant=Variant(chrom="chr1", pos=100, ref="A", alt="T"),
            organism="Homo sapiens",
            assembly="GRCh38",
        ))
        assert len(result.steps) >= 1

    def test_get_sequence_has_steps(self):
        result = self._svc().get_sequence(SequenceFetchRequest(
            organism="Homo sapiens", assembly="GRCh38",
            chrom="chr1", start=0, end=100,
        ))
        assert len(result.steps) >= 1

    def test_resolve_entity_has_steps(self):
        result = self._svc().resolve_entity(EntityResolveRequest(
            identifier="BRCA1", organism="Homo sapiens"
        ))
        assert len(result.steps) >= 1

    def test_liftover_has_steps(self):
        result = self._svc().liftover(LiftoverRequest(
            intervals=[GenomicInterval(chrom="chr1", start=0, end=100, assembly="GRCh38")],
            source_assembly="GRCh38",
            target_assembly="GRCh37",
            organism="Homo sapiens",
        ))
        assert len(result.steps) >= 1

    def test_annotate_has_steps(self):
        result = self._svc().annotate(AnnotationRequest(
            organism="Homo sapiens", assembly="GRCh38"
        ))
        assert len(result.steps) >= 1


# ---------------------------------------------------------------------------
# Custom catalog injection
# ---------------------------------------------------------------------------


class TestCustomCatalog:
    def test_service_with_custom_catalog(self):
        tiny_catalog = {
            "TestAsm": AssemblyInfo(
                name="TestAsm",
                organism="TestOrganism",
                organism_class=OrganismClass.PROKARYOTE,
                contigs={
                    "ctg1": ContigInfo(
                        name="ctg1", length=5000, topology=Topology.CIRCULAR
                    )
                },
            )
        }
        tiny_profiles = {
            "TestOrganism": SpeciesProfile(
                organism="TestOrganism",
                organism_class=OrganismClass.PROKARYOTE,
                default_assembly="TestAsm",
            )
        }
        svc = ReferenceGenomeService(
            assembly_catalog=tiny_catalog,
            species_profiles=tiny_profiles,
        )
        result = svc.list_supported_references()
        assert result.outcome is ServiceOutcome.OK
        assert any(a.name == "TestAsm" for a in result.value.assemblies)

    def test_custom_catalog_does_not_know_grch38(self):
        svc = ReferenceGenomeService(
            assembly_catalog={"MinimalAsm": AssemblyInfo(
                name="MinimalAsm",
                organism="Fake",
                organism_class=OrganismClass.PROKARYOTE,
            )},
            species_profiles={},
        )
        result = svc.validate_variant(VariantValidationRequest(
            variant=Variant(chrom="chr1", pos=0, ref="A", alt="T"),
            organism="Homo sapiens",
            assembly="GRCh38",
        ))
        assert result.outcome is ServiceOutcome.UNSUPPORTED
