"""Coordinate contract tests (Wave 0).

Covers convention round-trips, circular-aware interval math, strand handling, and the
enforced validation rules of `coordinate_systems.md` §6. Coordinate-error rate is a
zero-tolerance guardrail (`success_metrics.md` D1), so these are P0.
"""

import pytest
from cellxp.domain.coordinates import (
    interval_contains,
    interval_from_canonical,
    interval_length,
    interval_to_canonical,
    is_origin_crossing,
    normalize_position,
    opposite_strand,
    position_from_canonical,
    position_to_canonical,
)
from cellxp.domain.enums import CoordinateSystem, Strand, Topology
from cellxp.domain.errors import CoordinateError
from cellxp.domain.models import GenomicInterval, Variant
from cellxp.domain.validators.coordinates import (
    check_reference_allele,
    validate_interval,
    validate_variant_position,
)

ONE_BASED = CoordinateSystem.ONE_BASED_INCLUSIVE
CANON = CoordinateSystem.ZERO_BASED_HALF_OPEN


# --- convention round-trips -------------------------------------------------------------


def test_position_one_based_to_canonical_and_back():
    # VCF POS 100 (1-based) -> canonical 99 -> back to 100.
    canon = position_to_canonical(100, ONE_BASED)
    assert canon == 99
    assert position_from_canonical(canon, ONE_BASED) == 100


def test_interval_one_based_inclusive_to_canonical_half_open():
    # 1-based inclusive [100, 200] -> 0-based half-open [99, 200); length 101.
    start, end = interval_to_canonical(100, 200, ONE_BASED)
    assert (start, end) == (99, 200)
    assert interval_length(start, end) == 101
    assert interval_from_canonical(start, end, ONE_BASED) == (100, 200)


def test_canonical_system_is_identity():
    assert interval_to_canonical(10, 20, CANON) == (10, 20)
    assert position_to_canonical(10, CANON) == 10


@pytest.mark.parametrize("bad", [0, -5])
def test_one_based_position_must_be_at_least_one(bad):
    with pytest.raises(CoordinateError):
        position_to_canonical(bad, ONE_BASED)


# --- circular-aware math ----------------------------------------------------------------


def test_origin_crossing_detection():
    assert is_origin_crossing(4800, 200) is True
    assert is_origin_crossing(100, 200) is False


def test_circular_interval_length_wraps():
    # On a 5000 bp circle, [4800, 200) covers 4800..5000 and 0..200 => 400 bp.
    length = interval_length(4800, 200, topology=Topology.CIRCULAR, contig_length=5000)
    assert length == 400


def test_circular_length_requires_contig_length():
    with pytest.raises(CoordinateError):
        interval_length(4800, 200, topology=Topology.CIRCULAR)


def test_linear_length_rejects_inverted_interval():
    with pytest.raises(CoordinateError):
        interval_length(200, 100, topology=Topology.LINEAR)


def test_interval_contains_linear_half_open():
    assert interval_contains(100, 200, 100) is True  # start inclusive
    assert interval_contains(100, 200, 199) is True
    assert interval_contains(100, 200, 200) is False  # end exclusive


def test_interval_contains_circular():
    kw = {"topology": Topology.CIRCULAR, "contig_length": 5000}
    assert interval_contains(4800, 200, 4900, **kw) is True
    assert interval_contains(4800, 200, 50, **kw) is True
    assert interval_contains(4800, 200, 1000, **kw) is False


def test_normalize_position_modular():
    assert normalize_position(5200, 5000) == 200
    assert normalize_position(-1, 5000) == 4999


# --- strand -----------------------------------------------------------------------------


def test_opposite_strand():
    assert opposite_strand(Strand.PLUS) is Strand.MINUS
    assert opposite_strand("-") is Strand.PLUS
    assert opposite_strand(Strand.UNSTRANDED) is Strand.UNSTRANDED


# --- model intrinsic invariants ---------------------------------------------------------


def test_genomic_interval_rejects_negative():
    with pytest.raises(ValueError):
        GenomicInterval(chrom="chr1", start=-1, end=10)


def test_genomic_interval_rejects_bad_strand():
    with pytest.raises(ValueError):
        GenomicInterval(chrom="chr1", start=1, end=10, strand="x")


def test_variant_rejects_negative_position():
    with pytest.raises(ValueError):
        Variant(chrom="chr1", pos=-1, ref="A", alt="T")


# --- validator rules (coordinate_systems.md §6) -----------------------------------------


def test_validate_interval_linear_ok():
    iv = GenomicInterval(chrom="chr1", start=100, end=200, assembly="GRCh38")
    assert validate_interval(iv, topology=Topology.LINEAR) is iv


def test_validate_interval_linear_rejects_origin_crossing():
    iv = GenomicInterval(chrom="chr1", start=200, end=100)
    with pytest.raises(CoordinateError):
        validate_interval(iv, topology=Topology.LINEAR)


def test_validate_interval_circular_allows_origin_crossing():
    iv = GenomicInterval(chrom="chromosome", start=4800, end=200)
    assert validate_interval(iv, topology=Topology.CIRCULAR, contig_length=5000) is iv


def test_validate_interval_rejects_out_of_bounds():
    iv = GenomicInterval(chrom="chr1", start=100, end=6000)
    with pytest.raises(CoordinateError):
        validate_interval(iv, topology=Topology.LINEAR, contig_length=5000)


def test_validate_variant_position_bounds():
    v = Variant(chrom="chr1", pos=4999, ref="A", alt="T", assembly="bsub")
    assert validate_variant_position(v, contig_length=5000) is v
    with pytest.raises(CoordinateError):
        validate_variant_position(
            Variant(chrom="chr1", pos=5000, ref="A", alt="T"), contig_length=5000
        )


def test_reference_allele_check():
    v = Variant(chrom="chr1", pos=99, ref="a", alt="T", assembly="GRCh38")
    assert check_reference_allele(v, "A") is v  # case-insensitive match
    with pytest.raises(CoordinateError):
        check_reference_allele(v, "G")
