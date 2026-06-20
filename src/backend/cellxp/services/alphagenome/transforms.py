"""Coordinate framing, allele substitution, and delta helpers for sequence models.

All transforms are pure functions (no I/O) so they can be unit-tested independently
of the model backend. They follow `coordinate_systems.md`: canonical 0-based half-open
internally; strand handling is explicit; no silent conversions.
"""

from __future__ import annotations

from cellxp.domain.enums import Strand
from cellxp.domain.errors import CoordinateError
from cellxp.domain.models import Variant
from cellxp.services.reference.genome import AssemblyInfo

#: Default context window in bp (AlphaGenome v1 uses 131,072; Evo 2 uses variable).
DEFAULT_WINDOW_BP = 131_072


def frame_sequence_window(
    variant: Variant,
    *,
    assembly_info: AssemblyInfo,
    window_bp: int = DEFAULT_WINDOW_BP,
) -> tuple[int, int]:
    """Compute a canonical [start, end) window centered on `variant.pos`.

    The window is clamped to [0, contig_length] for linear contigs. Circular
    contigs may produce an origin-crossing interval (start > end) per
    `coordinate_systems.md` §5.

    Returns:
        (start, end) in canonical 0-based half-open coordinates.

    Raises:
        CoordinateError: if the contig is unknown or window_bp < 1.
    """
    if window_bp < 1:
        raise CoordinateError("window_bp must be >= 1", field="window_bp", value=window_bp)

    contig = assembly_info.get_contig(variant.chrom)
    if contig is None:
        raise CoordinateError(
            f"contig {variant.chrom!r} not found in assembly {assembly_info.name!r}",
            field="chrom",
            value=variant.chrom,
        )

    half = window_bp // 2
    raw_start = variant.pos - half
    raw_end = variant.pos + (window_bp - half)  # handle odd window_bp

    if contig.length is not None:
        # Linear contig: clamp to [0, contig_length].
        start = max(0, raw_start)
        end = min(contig.length, raw_end)
    else:
        # Length unknown: clamp start to 0, leave end unclamped.
        start = max(0, raw_start)
        end = raw_end

    return start, end


def substitute_allele(seq: str, pos_in_window: int, ref: str, alt: str) -> str:
    """Apply a ref→alt single-base (or multi-base) substitution in a sequence window.

    Args:
        seq: reference sequence string for the window (0-based).
        pos_in_window: 0-based position of the variant within `seq`.
        ref: reference allele to replace (length must match `seq[pos_in_window:]` prefix).
        alt: alternate allele to insert.

    Returns:
        Alternate sequence of the same total length as `seq` (truncated or padded with
        N's if the allele lengths differ, to preserve window size for model inputs).

    Raises:
        CoordinateError: if `pos_in_window` is out of range or ref allele mismatches.
    """
    if pos_in_window < 0 or pos_in_window >= len(seq):
        raise CoordinateError(
            f"pos_in_window ({pos_in_window}) is out of range for window of length {len(seq)}",
            field="pos_in_window",
            value=pos_in_window,
        )
    actual_ref = seq[pos_in_window : pos_in_window + len(ref)]
    if actual_ref.upper() != ref.upper():
        raise CoordinateError(
            f"ref-allele mismatch at pos_in_window {pos_in_window}: "
            f"window has {actual_ref!r}, expected {ref!r}",
            field="ref",
            value=ref,
        )
    prefix = seq[:pos_in_window]
    suffix = seq[pos_in_window + len(ref):]
    alt_seq = prefix + alt + suffix
    # Preserve window length for fixed-context models: pad or truncate.
    if len(alt_seq) < len(seq):
        alt_seq = alt_seq + "N" * (len(seq) - len(alt_seq))
    elif len(alt_seq) > len(seq):
        alt_seq = alt_seq[: len(seq)]
    return alt_seq


def compute_deltas(
    ref_scores: list[float],
    alt_scores: list[float],
) -> list[float]:
    """Element-wise `delta = alt - ref` across parallel score arrays."""
    if len(ref_scores) != len(alt_scores):
        raise ValueError(
            f"ref_scores and alt_scores must have the same length "
            f"({len(ref_scores)} vs {len(alt_scores)})"
        )
    return [a - r for r, a in zip(ref_scores, alt_scores)]


def variant_id(variant: Variant) -> str:
    """Canonical human-readable identifier for a variant."""
    return f"{variant.chrom}:{variant.pos + 1}:{variant.ref}>{variant.alt}"


def pos_in_window(variant_pos: int, window_start: int) -> int:
    """Offset of a canonical 0-based variant position within a sequence window."""
    offset = variant_pos - window_start
    if offset < 0:
        raise CoordinateError(
            f"variant position {variant_pos} is before window start {window_start}",
            field="variant_pos",
            value=variant_pos,
        )
    return offset
