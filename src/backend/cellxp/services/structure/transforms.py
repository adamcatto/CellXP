"""Pure transforms for the structure service (X3).

Task classification, model selection, and confidence derivation — all deterministic and
side-effect-free so they are trivially unit-testable without any model backend.
"""

from __future__ import annotations

from cellxp.domain.enums import ConfidenceBand, SequenceAlphabet
from cellxp.domain.models import GenomicInterval
from cellxp.domain.sequences import BiologicalSequence

from .schemas import LOW_CONFIDENCE_THRESHOLD, Span, StructureKind

#: Nucleic-acid alphabets accepted for ``nucleic_acid`` structure tasks.
_NUCLEIC = frozenset({SequenceAlphabet.DNA, SequenceAlphabet.RNA})


def classify_structure_task(
    *,
    sequences: list[BiologicalSequence],
    interval: GenomicInterval | None,
    has_ligand: bool = False,
    hint: str | None = None,
) -> StructureKind | None:
    """Classify the structure task from the available inputs (`structure_prediction.md` §4.1).

    An explicit, valid `hint` (e.g. carried on the subtask) always wins. Otherwise:
    a ligand or multiple protein chains → ``complex``; a single protein chain → ``protein``;
    nucleic-acid chains → ``nucleic_acid``; a bare genomic interval → ``contacts`` (chromatin
    contacts; request ``dna_shape`` explicitly via a hint). Returns None when nothing in the
    inputs determines a task.
    """
    if hint in ("protein", "nucleic_acid", "complex", "dna_shape", "contacts"):
        return hint  # type: ignore[return-value]

    if sequences:
        alphabets = {s.alphabet for s in sequences}
        if alphabets <= _NUCLEIC:
            return "nucleic_acid"
        # any protein chain present
        if has_ligand or len(sequences) > 1:
            return "complex"
        return "protein"

    if interval is not None:
        return "contacts"

    return None


def validate_kind_alphabet(
    kind: str, sequences: list[BiologicalSequence]
) -> str | None:
    """Return an error message when sequence alphabets are wrong for `kind`, else None.

    `protein`/`complex` require at least one protein chain; `nucleic_acid` requires every
    chain to be DNA/RNA. (The domain validates each sequence's own alphabet; here we check
    it is consistent with the *requested* structure task.)
    """
    if kind in ("protein", "complex"):
        if not sequences:
            return f"{kind} structure requires at least one protein sequence"
        if not any(s.alphabet is SequenceAlphabet.PROTEIN for s in sequences):
            return f"{kind} structure requires a protein chain; got only nucleic-acid input"
        return None

    if kind == "nucleic_acid":
        if not sequences:
            return "nucleic_acid structure requires at least one DNA/RNA sequence"
        if any(s.alphabet is SequenceAlphabet.PROTEIN for s in sequences):
            return "nucleic_acid structure cannot accept a protein chain"
        return None

    return None


def select_structure_model(
    kind: str, *, n_chains: int, has_ligand: bool
) -> str:
    """Pick the structure model for a prediction task (`structure_prediction.md` §3).

    Single protein monomer → ESMFold (fast). Complex/multimer, any ligand, or
    nucleic-acid-aware structure → Boltz-2 (higher fidelity, affinity-capable).
    """
    if kind in ("complex", "nucleic_acid") or has_ligand or n_chains > 1:
        return "boltz2"
    if kind == "protein":
        return "esmfold"
    return "unsupported"


def low_confidence_spans(
    per_residue: list[float], *, threshold: float = LOW_CONFIDENCE_THRESHOLD
) -> list[Span]:
    """Collapse runs of residues at/below `threshold` into half-open `Span`s.

    `per_residue` is pLDDT-style confidence normalized to ``[0, 1]``; positions are
    0-based. Returns disjoint, ordered spans of contiguous low-confidence residues.
    """
    spans: list[Span] = []
    run_start: int | None = None
    for i, c in enumerate(per_residue):
        if c <= threshold:
            if run_start is None:
                run_start = i
        elif run_start is not None:
            spans.append(Span(start=run_start, end=i, label="low_confidence"))
            run_start = None
    if run_start is not None:
        spans.append(Span(start=run_start, end=len(per_residue), label="low_confidence"))
    return spans


def mean_confidence_band(per_residue: list[float]) -> ConfidenceBand:
    """Map mean per-residue confidence (``[0, 1]``) to a qualitative band.

    Mirrors pLDDT bands: mean ≥ 0.90 → HIGH, ≥ 0.70 → MEDIUM, > 0 → LOW, empty → UNKNOWN.
    """
    if not per_residue:
        return ConfidenceBand.UNKNOWN
    mean = sum(per_residue) / len(per_residue)
    if mean >= 0.90:
        return ConfidenceBand.HIGH
    if mean >= 0.70:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW
