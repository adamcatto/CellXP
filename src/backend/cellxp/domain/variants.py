"""Variant notation parsing and edge normalization.

Detects and parses variant surface syntax (rsID, VCF-ish, genomic HGVS substitution) into
the canonical `Variant` (`input_normalizer.md` step 1-3). Coordinate-bearing notations are
converted to the **canonical 0-based** position via `domain/coordinates.py`; organism and
assembly are **not** assumed here (that is `entity_resolver`'s job) — only what is present
in the notation is recorded.

v0 scope: SNV/MNV substitutions. Indel/del/ins/dup HGVS forms raise an explicit
`VariantError` rather than being mis-parsed.
"""

from __future__ import annotations

import re

from .coordinates import position_to_canonical
from .enums import CoordinateSystem, VariantNotation
from .errors import VariantError
from .models import Variant
from .validators.alleles import validate_variant_alleles

_RSID_RE = re.compile(r"^rs\d+$", re.IGNORECASE)
_HGVS_G_RE = re.compile(
    r"^(?P<acc>[A-Za-z0-9_.]+):g\.(?P<pos>\d+)(?P<ref>[ACGTNacgtn]+)>(?P<alt>[ACGTNacgtn]+)$"
)
_VCF_SPLIT_RE = re.compile(r"[\s:\-]+")


def detect_variant_notation(raw: str) -> VariantNotation:
    """Classify a variant string's surface syntax. Raises `VariantError` if unrecognized."""
    s = raw.strip()
    if _RSID_RE.match(s):
        return VariantNotation.RSID
    if ":g." in s:
        return VariantNotation.HGVS_GENOMIC
    if len(_VCF_SPLIT_RE.split(s)) == 4:
        return VariantNotation.VCF
    raise VariantError(f"unrecognized variant notation: {raw!r}", field="variant", value=raw)


def parse_rsid(raw: str) -> str:
    """Normalize a dbSNP rsID to lowercase `rs<digits>`.

    An rsID carries no coordinates on its own; resolution to a positioned `Variant` is
    `entity_resolver`'s job (`FR-4`), so this returns the canonical identifier string only.
    """
    s = raw.strip()
    if not _RSID_RE.match(s):
        raise VariantError(f"not a valid rsID: {raw!r}", field="rsid", value=raw)
    return "rs" + s[2:]


def parse_vcf_variant(
    raw: str, *, system: CoordinateSystem = CoordinateSystem.ONE_BASED_INCLUSIVE
) -> Variant:
    """Parse `chrom pos ref alt` (1-based by default) into a canonical `Variant`.

    Accepts whitespace, colon, or dash separators. POS is converted to canonical 0-based.
    """
    parts = _VCF_SPLIT_RE.split(raw.strip())
    if len(parts) != 4:
        raise VariantError(
            f"VCF-style variant needs chrom/pos/ref/alt; got {raw!r}", field="variant", value=raw
        )
    chrom, pos_str, ref, alt = parts
    try:
        pos = int(pos_str)
    except ValueError as exc:
        raise VariantError(f"variant position is not an integer: {pos_str!r}", field="pos") from exc
    ref_n, alt_n = validate_variant_alleles(ref, alt)
    canonical_pos = position_to_canonical(pos, system)
    return Variant(chrom=chrom, pos=canonical_pos, ref=ref_n, alt=alt_n)


def parse_hgvs_genomic(raw: str) -> Variant:
    """Parse a genomic HGVS substitution `ACC:g.POSref>alt` into a canonical `Variant`.

    The accession is recorded as `assembly` (it identifies the reference sequence); HGVS
    `g.` positions are 1-based and converted to canonical 0-based. Only substitutions are
    supported in v0.
    """
    m = _HGVS_G_RE.match(raw.strip())
    if not m:
        raise VariantError(
            f"unsupported or malformed genomic HGVS (v0 supports g. substitutions only): {raw!r}",
            field="variant",
            value=raw,
        )
    ref_n, alt_n = validate_variant_alleles(m["ref"], m["alt"])
    canonical_pos = position_to_canonical(int(m["pos"]), CoordinateSystem.ONE_BASED_INCLUSIVE)
    return Variant(chrom=m["acc"], pos=canonical_pos, ref=ref_n, alt=alt_n, assembly=m["acc"])


def normalize_variant(raw: str) -> Variant:
    """Parse any coordinate-bearing variant notation into a canonical `Variant`.

    rsIDs are rejected here because they have no coordinates until resolved — call
    `parse_rsid` and resolve via `entity_resolver` instead.
    """
    notation = detect_variant_notation(raw)
    if notation is VariantNotation.RSID:
        raise VariantError(
            f"rsID {raw!r} has no coordinates until resolved; use parse_rsid + entity_resolver",
            field="variant",
            value=raw,
        )
    if notation is VariantNotation.HGVS_GENOMIC:
        return parse_hgvs_genomic(raw)
    return parse_vcf_variant(raw)
