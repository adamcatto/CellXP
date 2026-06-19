"""Canonical coordinate conversions and circular-aware interval math.

This is the **single, tested utility** every coordinate crossing a boundary (input parse,
model call, artifact, report, liftover) goes through — never ad hoc
(`coordinate_systems.md` §3). The internal canonical representation is **0-based,
half-open `[start, end)`** for ranges (BED-style); user-facing formats (VCF/GFF/browser
are 1-based inclusive) are converted at the edges.

Circular contigs (common in bacteria/archaea, `coordinate_systems.md` §5) are represented
with an **origin-crossing** interval where `start >= end`: e.g. on a 5000 bp circle,
`[4800, 200)` covers 4800..5000 and 0..200. Origin-crossing is only valid on circular
contigs; the linear/circular distinction is enforced in `validators/coordinates.py`.

Functions here do pure arithmetic and raise `CoordinateError` on inconsistent input; they
never silently coerce (`NFR-3`).
"""

from __future__ import annotations

from .enums import CoordinateSystem, Strand, Topology
from .errors import CoordinateError

# --- position conversions (single point, e.g. a variant POS) ----------------------------


def position_to_canonical(pos: int, system: CoordinateSystem) -> int:
    """Convert a single position to the canonical 0-based coordinate.

    A 1-based inclusive position `p` maps to 0-based `p - 1` (e.g. VCF POS).
    """
    if system is CoordinateSystem.ZERO_BASED_HALF_OPEN:
        if pos < 0:
            raise CoordinateError("0-based position must be non-negative", field="pos", value=pos)
        return pos
    if system is CoordinateSystem.ONE_BASED_INCLUSIVE:
        if pos < 1:
            raise CoordinateError("1-based position must be >= 1", field="pos", value=pos)
        return pos - 1
    raise CoordinateError(f"unknown coordinate system: {system!r}", field="system", value=system)


def position_from_canonical(pos: int, system: CoordinateSystem) -> int:
    """Convert a canonical 0-based position back to `system` for display/export."""
    if pos < 0:
        raise CoordinateError("canonical position must be non-negative", field="pos", value=pos)
    if system is CoordinateSystem.ZERO_BASED_HALF_OPEN:
        return pos
    if system is CoordinateSystem.ONE_BASED_INCLUSIVE:
        return pos + 1
    raise CoordinateError(f"unknown coordinate system: {system!r}", field="system", value=system)


# --- interval conversions ---------------------------------------------------------------


def interval_to_canonical(start: int, end: int, system: CoordinateSystem) -> tuple[int, int]:
    """Convert a `(start, end)` pair in `system` to canonical 0-based half-open.

    1-based inclusive `[s, e]` -> 0-based half-open `[s - 1, e)`.
    """
    if system is CoordinateSystem.ZERO_BASED_HALF_OPEN:
        return start, end
    if system is CoordinateSystem.ONE_BASED_INCLUSIVE:
        return position_to_canonical(start, system), end
    raise CoordinateError(f"unknown coordinate system: {system!r}", field="system", value=system)


def interval_from_canonical(start: int, end: int, system: CoordinateSystem) -> tuple[int, int]:
    """Convert a canonical 0-based half-open interval back to `system` for display."""
    if system is CoordinateSystem.ZERO_BASED_HALF_OPEN:
        return start, end
    if system is CoordinateSystem.ONE_BASED_INCLUSIVE:
        return position_from_canonical(start, system), end
    raise CoordinateError(f"unknown coordinate system: {system!r}", field="system", value=system)


# --- circular-aware interval math -------------------------------------------------------


def is_origin_crossing(start: int, end: int) -> bool:
    """Whether a canonical interval wraps a circular origin (i.e. `start >= end`)."""
    return start >= end


def normalize_position(pos: int, contig_length: int) -> int:
    """Wrap a position onto `[0, contig_length)` for a circular contig (modular)."""
    if contig_length <= 0:
        raise CoordinateError(
            "contig_length must be positive", field="contig_length", value=contig_length
        )
    return pos % contig_length


def interval_length(
    start: int,
    end: int,
    *,
    topology: Topology = Topology.LINEAR,
    contig_length: int | None = None,
) -> int:
    """Length of a canonical interval, circular-aware.

    Linear: `end - start`. Circular origin-crossing (`start >= end`): the wrap length
    `(contig_length - start) + end`, which requires `contig_length`.
    """
    if topology is Topology.LINEAR or not is_origin_crossing(start, end):
        if start > end:
            raise CoordinateError(
                f"linear interval start ({start}) must be <= end ({end})",
                field="start",
                value=start,
            )
        return end - start
    if contig_length is None:
        raise CoordinateError(
            "origin-crossing interval length requires contig_length", field="contig_length"
        )
    return (contig_length - start) + end


def interval_contains(
    start: int,
    end: int,
    pos: int,
    *,
    topology: Topology = Topology.LINEAR,
    contig_length: int | None = None,
) -> bool:
    """Whether canonical position `pos` lies in canonical half-open interval `[start, end)`.

    For circular origin-crossing intervals, containment is the union of `[start, length)`
    and `[0, end)`.
    """
    if topology is Topology.LINEAR or not is_origin_crossing(start, end):
        return start <= pos < end
    if contig_length is not None:
        pos = normalize_position(pos, contig_length)
        return pos >= start or pos < end
    return pos >= start or pos < end


# --- strand -----------------------------------------------------------------------------


def opposite_strand(strand: Strand | str) -> Strand:
    """Flip strand. `UNSTRANDED` ('.') flips to itself."""
    strand = Strand(strand)
    if strand is Strand.PLUS:
        return Strand.MINUS
    if strand is Strand.MINUS:
        return Strand.PLUS
    return Strand.UNSTRANDED
