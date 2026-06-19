"""Domain error hierarchy for CellXP.

Validation failures are **actionable errors surfaced to the user** (`FR-10`), never
silently corrected (`coordinate_systems.md` §6). A silent coordinate error is a
release-blocking P0 (`NFR-3`), so coordinate problems raise rather than coerce.
"""

from __future__ import annotations


class CellXPError(Exception):
    """Base class for all CellXP domain errors."""


class DomainValidationError(CellXPError):
    """A user-actionable validation failure.

    Carries an optional `field` and `value` so the interface can surface a precise,
    actionable message (`FR-10`).
    """

    def __init__(self, message: str, *, field: str | None = None, value: object = None) -> None:
        super().__init__(message)
        self.field = field
        self.value = value


class CoordinateError(DomainValidationError):
    """Invalid or inconsistent genomic coordinate, assembly, strand, or topology.

    Raised by `domain/coordinates.py` and `domain/validators/coordinates.py` for any
    violation of the canonical coordinate invariants (`coordinate_systems.md` §6).
    """


class SequenceError(DomainValidationError):
    """Malformed biological sequence: bad alphabet, empty, or unparseable FASTA."""


class VariantError(DomainValidationError):
    """Malformed or unparseable variant notation, or invalid alleles."""


class IntegrityError(CellXPError):
    """Stored content does not match its recorded hash (`provenance_model.md` §6, PROV-4).

    Raised on read from the object store when a payload's `sha256` differs from the hash
    captured in its `Step`/`ArtifactRef` provenance — i.e. corruption or tampering. Not a
    user-validation error: it signals a data-integrity fault in the store itself.
    """

    def __init__(self, message: str, *, key: str | None = None) -> None:
        super().__init__(message)
        self.key = key
