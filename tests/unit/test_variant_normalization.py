"""Variant normalization contract tests (Wave 0).

Covers notation detection, VCF/HGVS parsing with 1-based -> canonical 0-based conversion,
allele validation, and assembly/organism name canonicalization. Coordinate conversions
feed the zero-tolerance coordinate guardrail (`success_metrics.md` D1), so these are P0.
"""

import pytest

from cellxp.domain.enums import OrganismClass, VariantNotation
from cellxp.domain.errors import DomainValidationError, VariantError
from cellxp.domain.validators.alleles import validate_allele, validate_variant_alleles
from cellxp.domain.validators.assembly import is_known_alias, normalize_assembly_name
from cellxp.domain.validators.species import normalize_organism_name, validate_organism_class
from cellxp.domain.variants import (
    detect_variant_notation,
    normalize_variant,
    parse_hgvs_genomic,
    parse_rsid,
    parse_vcf_variant,
)


# --- notation detection -----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("rs334", VariantNotation.RSID),
        ("chr1 12345 A T", VariantNotation.VCF),
        ("chr1:12345:A:T", VariantNotation.VCF),
        ("NC_000011.10:g.5226774T>A", VariantNotation.HGVS_GENOMIC),
    ],
)
def test_detect_variant_notation(raw, expected):
    assert detect_variant_notation(raw) is expected


def test_detect_unknown_raises():
    with pytest.raises(VariantError):
        detect_variant_notation("not a variant!!")


# --- rsID -------------------------------------------------------------------------------


def test_parse_rsid_normalizes_case():
    assert parse_rsid("RS334") == "rs334"


def test_parse_rsid_rejects_garbage():
    with pytest.raises(VariantError):
        parse_rsid("rsABC")


# --- VCF parsing + coordinate conversion ------------------------------------------------


def test_parse_vcf_converts_one_based_to_canonical():
    # VCF POS 12345 (1-based) -> canonical 0-based 12344.
    v = parse_vcf_variant("chr1 12345 A T")
    assert (v.chrom, v.pos, v.ref, v.alt) == ("chr1", 12344, "A", "T")
    assert v.assembly is None  # organism/assembly not assumed here


def test_parse_vcf_colon_separated():
    v = parse_vcf_variant("chr1:12345:a:t")
    assert (v.pos, v.ref, v.alt) == (12344, "A", "T")


def test_parse_vcf_rejects_noninteger_pos():
    with pytest.raises(VariantError):
        parse_vcf_variant("chr1 X A T")


def test_parse_vcf_rejects_wrong_field_count():
    with pytest.raises(VariantError):
        parse_vcf_variant("chr1 12345 A")


# --- genomic HGVS -----------------------------------------------------------------------


def test_parse_hgvs_genomic_records_accession_as_assembly():
    v = parse_hgvs_genomic("NC_000011.10:g.5226774T>A")
    assert v.assembly == "NC_000011.10"
    assert v.pos == 5226773  # 1-based 5226774 -> canonical 0-based
    assert (v.ref, v.alt) == ("T", "A")


def test_parse_hgvs_unsupported_form_raises():
    with pytest.raises(VariantError):
        parse_hgvs_genomic("NC_000011.10:g.5226774del")


# --- dispatch ---------------------------------------------------------------------------


def test_normalize_variant_dispatches():
    assert normalize_variant("chr1:12345:A:T").pos == 12344
    assert normalize_variant("NC_000011.10:g.5226774T>A").assembly == "NC_000011.10"


def test_normalize_variant_rejects_bare_rsid():
    with pytest.raises(VariantError):
        normalize_variant("rs334")


# --- alleles ----------------------------------------------------------------------------


def test_validate_allele_uppercases():
    assert validate_allele("acgt") == "ACGT"


def test_validate_allele_rejects_non_dna():
    with pytest.raises(VariantError):
        validate_allele("ACXT")


def test_validate_variant_alleles_rejects_identical():
    with pytest.raises(VariantError):
        validate_variant_alleles("A", "A")


# --- assembly / organism canonicalization -----------------------------------------------


@pytest.mark.parametrize(
    "alias,canonical",
    [("hg38", "GRCh38"), ("GRCh38", "GRCh38"), ("hg19", "GRCh37"), ("mm39", "GRCm39")],
)
def test_normalize_assembly_aliases(alias, canonical):
    assert normalize_assembly_name(alias) == canonical


def test_unknown_assembly_passes_through():
    assert normalize_assembly_name("GCF_000005845.2") == "GCF_000005845.2"
    assert is_known_alias("GCF_000005845.2") is False


def test_normalize_organism_aliases():
    assert normalize_organism_name("Homo sapiens") == "human"
    assert normalize_organism_name("Mus musculus") == "mouse"


def test_validate_organism_class():
    assert validate_organism_class("prokaryote") is OrganismClass.PROKARYOTE
    with pytest.raises(DomainValidationError):
        validate_organism_class("alien")
