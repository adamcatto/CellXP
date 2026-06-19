"""Sequence validators — alphabet enforcement (`input_normalizer.md` step 2).

Separate from `domain/sequences.py` (which normalizes/parses) so the public entry point
returns a validated `BiologicalSequence` or raises an actionable `SequenceError` (`FR-10`).
"""

from __future__ import annotations

from ..enums import SequenceAlphabet
from ..errors import SequenceError
from ..sequences import (
    ALPHABET_CHARS,
    BiologicalSequence,
    detect_alphabet,
    is_ambiguous,
    normalize_sequence,
)


def validate_sequence(
    raw: str,
    alphabet: SequenceAlphabet | None = None,
    *,
    allow_ambiguous: bool = True,
    seq_id: str | None = None,
) -> BiologicalSequence:
    """Validate and normalize a raw sequence against an alphabet.

    If `alphabet` is None it is auto-detected. Every character must be in the alphabet's
    IUPAC vocabulary; when `allow_ambiguous` is False, non-core ambiguity codes are
    rejected too. Raises `SequenceError` on any violation; nothing is silently dropped.
    """
    seq = normalize_sequence(raw)
    if not seq:
        raise SequenceError("empty sequence", field="seq", value=raw)
    if alphabet is None:
        alphabet = detect_alphabet(seq)

    illegal = set(seq) - ALPHABET_CHARS[alphabet]
    if illegal:
        raise SequenceError(
            f"characters {sorted(illegal)} are not valid in a {alphabet.value} sequence",
            field="seq",
            value=raw,
        )
    if not allow_ambiguous and is_ambiguous(seq, alphabet):
        raise SequenceError(
            f"{alphabet.value} sequence contains ambiguity codes but allow_ambiguous=False",
            field="seq",
            value=raw,
        )
    return BiologicalSequence(seq=seq, alphabet=alphabet, seq_id=seq_id)
