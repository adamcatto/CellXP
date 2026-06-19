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
