"""Coordinate validators — the enforced rules of `coordinate_systems.md` §6.

These validate a positioned entity against external facts (assembly topology, contig
bounds, the reference base at a position). They are deliberately separate from
`domain/models.py` (which enforces only intrinsic invariants) because they need data from
the reference service (`services/reference/`).

Every failure raises `CoordinateError` with an actionable message (`FR-10`); nothing is
silently corrected (`NFR-3`).
"""

from __future__ import annotations

from ..coordinates import is_origin_crossing
from ..enums import Strand, Topology
from ..errors import CoordinateError
from ..models import GenomicInterval, Variant


def validate_interval(
    interval: GenomicInterval,
    *,
    topology: Topology = Topology.LINEAR,
    contig_length: int | None = None,
) -> GenomicInterval:
    """Validate a canonical interval against topology and (optional) contig bounds.

    Enforces (`coordinate_systems.md` §6):
    - strand is in the canonical vocabulary;
    - `start`/`end` non-negative (also guaranteed by the model);
    - linear contigs require `start <= end`; origin-crossing (`start >= end`) is allowed
      only on circular contigs;
    - when `contig_length` is known, coordinates lie within `[0, contig_length]`
      (the half-open `end` may equal the length).

    Returns the interval unchanged on success.
    """
    # Strand vocabulary (defensive; the model already coerces to Strand).
    try:
        Strand(interval.strand)
    except ValueError as exc:
        raise CoordinateError(
            f"strand must be one of +, -, .; got {interval.strand!r}",
            field="strand",
            value=interval.strand,
        ) from exc

    if interval.start < 0 or interval.end < 0:
        raise CoordinateError(
            "coordinates must be non-negative", field="start", value=interval.start
        )

    crossing = is_origin_crossing(interval.start, interval.end)
    if crossing and interval.start != interval.end:
        # start > end: only legal as a circular wrap.
        if topology is not Topology.CIRCULAR:
            raise CoordinateError(
                f"start ({interval.start}) > end ({interval.end}) is only valid on a circular "
                f"contig; {interval.chrom!r} is {topology.value}",
                field="start",
                value=interval.start,
            )

    if contig_length is not None:
        if contig_length <= 0:
            raise CoordinateError(
                "contig_length must be positive", field="contig_length", value=contig_length
            )
        for name, value in (("start", interval.start), ("end", interval.end)):
            if value > contig_length:
                raise CoordinateError(
                    f"{name} ({value}) exceeds contig length ({contig_length}) for "
                    f"{interval.chrom!r}",
                    field=name,
                    value=value,
                )

    return interval


def validate_variant_position(
    variant: Variant,
    *,
    contig_length: int | None = None,
) -> Variant:
    """Validate a variant's canonical position is in-bounds for its contig."""
    if variant.pos < 0:
        raise CoordinateError("variant position must be non-negative", field="pos", value=variant.pos)
    if contig_length is not None and variant.pos >= contig_length:
        raise CoordinateError(
            f"variant position ({variant.pos}) is outside contig length ({contig_length}) for "
            f"{variant.chrom!r}",
            field="pos",
            value=variant.pos,
        )
    return variant


def check_reference_allele(variant: Variant, observed_ref: str) -> Variant:
    """Reference-allele check: the variant's `ref` must match the reference base(s).

    `observed_ref` is the base(s) the reference service reports at the variant position for
    the named assembly (`coordinate_systems.md` §6). Case-insensitive; raises on mismatch
    rather than coercing — a mismatch usually means a wrong assembly or strand (R2/R4).
    """
    if variant.ref.upper() != observed_ref.upper():
        raise CoordinateError(
            f"reference-allele mismatch at {variant.chrom}:{variant.pos} "
            f"(assembly {variant.assembly}): variant ref {variant.ref!r} != reference "
            f"{observed_ref!r} — check assembly/strand",
            field="ref",
            value=variant.ref,
        )
    return variant
