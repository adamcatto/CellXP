"""Canonical domain enums for CellXP.

These vocabularies are part of the frozen domain contract (Wave 0). They name the
coordinate conventions, strands, and contig topologies that every positioned entity
in the system reasons about. See `documentation/explanation/coordinate_systems.md`.
"""

from __future__ import annotations

from enum import Enum


class Strand(str, Enum):
    """Strand of a positioned feature.

    `UNSTRANDED` (`.`) means strand is unknown or not meaningful for the feature;
    strand-aware operations must state how they use it (`coordinate_systems.md` §3).
    """

    PLUS = "+"
    MINUS = "-"
    UNSTRANDED = "."


class CoordinateSystem(str, Enum):
    """A coordinate convention an interval/position may be expressed in.

    `ZERO_BASED_HALF_OPEN` is the **internal canonical** representation used by every
    `GenomicInterval` (`coordinate_systems.md` §3). The others are edge formats that are
    converted to/from canonical via `domain/coordinates.py` — never compared ad hoc.
    """

    ZERO_BASED_HALF_OPEN = "0-based-half-open"  # BED-style; canonical internal
    ONE_BASED_INCLUSIVE = "1-based-inclusive"  # VCF / GFF / genome-browser display


class SequenceAlphabet(str, Enum):
    """The biological alphabet a sequence is written in (`input_normalizer.md` step 2)."""

    DNA = "dna"
    RNA = "rna"
    PROTEIN = "protein"


class Topology(str, Enum):
    """Whether a contig/assembly replicon is linear or circular.

    Topology is a property of the assembly, resolved by the reference service
    (`services/reference/`); circular wrap (origin-crossing) intervals are only valid on
    `CIRCULAR` contigs (`coordinate_systems.md` §5/§6).
    """

    LINEAR = "linear"
    CIRCULAR = "circular"
