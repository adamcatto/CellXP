"""Organism-name canonicalization and organism-class validation.

Lightweight Wave 0 helpers: canonicalize common organism names/aliases and validate an
`organism_class` against the controlled vocabulary (`supported_species.md` §1). The full
`SpeciesProfile`/`StrainProfile` registry (organism -> assembly -> applicable models) is
the reference service's responsibility and its storage is intentionally undecided in
Wave 0 (`supported_species.md` §5 TODO), so it is not built here.
"""

from __future__ import annotations

from ..enums import OrganismClass
from ..errors import DomainValidationError

# Canonical organism name keyed by lowercased alias.
_ORGANISM_ALIASES = {
    "human": "human",
    "homo sapiens": "human",
    "h. sapiens": "human",
    "hsapiens": "human",
    "mouse": "mouse",
    "mus musculus": "mouse",
    "m. musculus": "mouse",
}


def normalize_organism_name(name: str) -> str:
    """Canonicalize an organism name/alias; pass unknown names through trimmed."""
    trimmed = name.strip()
    return _ORGANISM_ALIASES.get(trimmed.lower(), trimmed)


def validate_organism_class(value: str) -> OrganismClass:
    """Coerce/validate a string into an `OrganismClass`, raising on an unknown class."""
    try:
        return OrganismClass(value.strip().lower())
    except ValueError as exc:
        allowed = ", ".join(c.value for c in OrganismClass)
        raise DomainValidationError(
            f"unknown organism_class {value!r}; expected one of: {allowed}",
            field="organism_class",
            value=value,
        ) from exc
