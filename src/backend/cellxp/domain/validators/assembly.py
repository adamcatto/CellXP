"""Assembly-name canonicalization.

Resolves common assembly aliases to a single canonical name so a downstream comparison
never confuses, e.g., hg19 with GRCh38 (an R2 silent-coordinate hazard). This does **not**
check whether the assembly exists or fetch its contigs/topology — that is the reference
service's job (`services/reference/`, `reference_genome_service.md`); the registry where
assemblies live is intentionally undecided in Wave 0 (`supported_species.md` §5 TODO).
Unknown names (e.g. RefSeq `GCF_*` accessions) pass through unchanged.
"""

from __future__ import annotations

# Canonical name keyed by lowercased alias.
_ASSEMBLY_ALIASES = {
    "grch38": "GRCh38",
    "hg38": "GRCh38",
    "grch37": "GRCh37",
    "hg19": "GRCh37",
    "grcm39": "GRCm39",
    "mm39": "GRCm39",
    "grcm38": "GRCm38",
    "mm10": "GRCm38",
}


def normalize_assembly_name(name: str) -> str:
    """Canonicalize an assembly name/alias; pass unknown accessions through trimmed."""
    trimmed = name.strip()
    return _ASSEMBLY_ALIASES.get(trimmed.lower(), trimmed)


def is_known_alias(name: str) -> bool:
    """Whether `name` matches a known human/mouse assembly alias."""
    return name.strip().lower() in _ASSEMBLY_ALIASES
