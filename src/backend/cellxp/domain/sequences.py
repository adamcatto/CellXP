"""Biological sequence types and edge normalization.

Turns pasted/uploaded sequence text into canonical, alphabet-tagged
`BiologicalSequence` values (`input_normalizer.md` steps 2-3): uppercase, whitespace
stripped, alphabet validated against IUPAC vocabularies. Ambiguity codes are kept and
annotated, never silently dropped.
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from .enums import SequenceAlphabet
from .errors import SequenceError

# IUPAC core + ambiguity vocabularies.
_DNA_CORE = set("ACGT")
_RNA_CORE = set("ACGU")
_NUC_AMBIGUITY = set("RYSWKMBDHVN")  # IUPAC nucleotide ambiguity codes
_PROTEIN_CORE = set("ACDEFGHIKLMNPQRSTVWY")  # 20 standard amino acids
_PROTEIN_EXTRA = set("BZJUOX*")  # ambiguous (B,Z,J), Sec/Pyl (U,O), unknown (X), stop (*)

CORE_CHARS: dict[SequenceAlphabet, set[str]] = {
    SequenceAlphabet.DNA: _DNA_CORE,
    SequenceAlphabet.RNA: _RNA_CORE,
    SequenceAlphabet.PROTEIN: _PROTEIN_CORE,
}
ALPHABET_CHARS: dict[SequenceAlphabet, set[str]] = {
    SequenceAlphabet.DNA: _DNA_CORE | _NUC_AMBIGUITY,
    SequenceAlphabet.RNA: _RNA_CORE | _NUC_AMBIGUITY,
    SequenceAlphabet.PROTEIN: _PROTEIN_CORE | _PROTEIN_EXTRA,
}

_DNA_COMPLEMENT = {
    "A": "T", "T": "A", "C": "G", "G": "C", "N": "N",
    "R": "Y", "Y": "R", "S": "S", "W": "W", "K": "M", "M": "K",
    "B": "V", "V": "B", "D": "H", "H": "D",
}
_RNA_COMPLEMENT = {**{k: v for k, v in _DNA_COMPLEMENT.items() if k != "T"}, "A": "U", "U": "A"}


def normalize_sequence(raw: str) -> str:
    """Canonicalize a raw sequence: strip all whitespace, uppercase."""
    return "".join(raw.split()).upper()


def is_ambiguous(seq: str, alphabet: SequenceAlphabet) -> bool:
    """Whether the (normalized) sequence contains any non-core IUPAC ambiguity code."""
    return bool(set(normalize_sequence(seq)) - CORE_CHARS[alphabet])


def detect_alphabet(seq: str) -> SequenceAlphabet:
    """Best-effort alphabet detection (`input_normalizer.md` open question: auto vs hint).

    Heuristic: any character that cannot be a nucleotide => protein; `U` without `T` => RNA;
    otherwise DNA. Short peptides made only of letters that double as nucleotide ambiguity
    codes are inherently ambiguous — callers should pass an explicit alphabet when known.
    """
    chars = set(normalize_sequence(seq))
    if not chars:
        raise SequenceError("empty sequence", field="seq", value=seq)
    nucleotide_space = _DNA_CORE | _RNA_CORE | _NUC_AMBIGUITY
    if chars - nucleotide_space:
        return SequenceAlphabet.PROTEIN
    if "U" in chars and "T" not in chars:
        return SequenceAlphabet.RNA
    return SequenceAlphabet.DNA


def reverse_complement(seq: str, alphabet: SequenceAlphabet) -> str:
    """Reverse complement a normalized nucleotide sequence (DNA/RNA only)."""
    if alphabet is SequenceAlphabet.PROTEIN:
        raise SequenceError("reverse_complement is undefined for protein", field="alphabet")
    table = _DNA_COMPLEMENT if alphabet is SequenceAlphabet.DNA else _RNA_COMPLEMENT
    s = normalize_sequence(seq)
    try:
        return "".join(table[b] for b in reversed(s))
    except KeyError as exc:
        raise SequenceError(
            f"cannot complement base {exc.args[0]!r} in {alphabet.value} sequence",
            field="seq",
        ) from exc


class BiologicalSequence(BaseModel):
    """A normalized, alphabet-tagged sequence (`input_normalizer.md` step 3)."""

    seq: str
    alphabet: SequenceAlphabet
    seq_id: str | None = None

    @field_validator("seq")
    @classmethod
    def _normalize(cls, v: str) -> str:
        norm = normalize_sequence(v)
        if not norm:
            raise ValueError("sequence must be non-empty")
        return norm


def parse_fasta(text: str) -> list[BiologicalSequence]:
    """Parse FASTA text into alphabet-detected `BiologicalSequence` records.

    Raises `SequenceError` on malformed input (e.g. body before any header).
    """
    records: list[BiologicalSequence] = []
    header: str | None = None
    body: list[str] = []

    def flush() -> None:
        if header is not None:
            seq = normalize_sequence("".join(body))
            records.append(BiologicalSequence(seq=seq, alphabet=detect_alphabet(seq), seq_id=header))

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            flush()
            header = line[1:].strip()
            body = []
        else:
            if header is None:
                raise SequenceError("FASTA body before any '>' header", field="fasta")
            body.append(line)
    flush()
    if not records:
        raise SequenceError("no FASTA records found", field="fasta")
    return records
