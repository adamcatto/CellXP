"""Allele validators — REF/ALT must be valid DNA and form an actual change.

Used by variant normalization (`domain/variants.py`) and the reference-allele check
(`validators/coordinates.py`). Raises actionable `VariantError` (`FR-10`).
"""

from __future__ import annotations

from ..errors import VariantError

_DNA_ALLELE = set("ACGTN")


def validate_allele(allele: str, *, allow_n: bool = True) -> str:
    """Normalize (uppercase) and validate a single allele as DNA bases."""
    norm = allele.strip().upper()
    if not norm:
        raise VariantError("allele must be non-empty", field="allele", value=allele)
    permitted = _DNA_ALLELE if allow_n else _DNA_ALLELE - {"N"}
    illegal = set(norm) - permitted
    if illegal:
        raise VariantError(
            f"allele {allele!r} contains non-DNA characters {sorted(illegal)}",
            field="allele",
            value=allele,
        )
    return norm


def validate_variant_alleles(ref: str, alt: str, *, allow_n: bool = True) -> tuple[str, str]:
    """Validate REF/ALT and ensure they describe an actual change (`ref != alt`)."""
    ref_n = validate_allele(ref, allow_n=allow_n)
    alt_n = validate_allele(alt, allow_n=allow_n)
    if ref_n == alt_n:
        raise VariantError(
            f"ref and alt are identical ({ref_n!r}); not a variant", field="alt", value=alt
        )
    return ref_n, alt_n
