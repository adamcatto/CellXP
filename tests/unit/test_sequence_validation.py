"""Sequence contract tests (Wave 0): normalization, alphabets, FASTA, reverse complement."""

import pytest

from cellxp.domain.enums import SequenceAlphabet
from cellxp.domain.errors import SequenceError
from cellxp.domain.sequences import (
    BiologicalSequence,
    detect_alphabet,
    is_ambiguous,
    normalize_sequence,
    parse_fasta,
    reverse_complement,
)
from cellxp.domain.validators.sequences import validate_sequence


def test_normalize_strips_whitespace_and_uppercases():
    assert normalize_sequence(" ac gt\n a ") == "ACGTA"


@pytest.mark.parametrize(
    "seq,expected",
    [
        ("ACGTACGT", SequenceAlphabet.DNA),
        ("ACGUACGU", SequenceAlphabet.RNA),
        ("MKLVEEFG", SequenceAlphabet.PROTEIN),  # E/F/L disambiguate
    ],
)
def test_detect_alphabet(seq, expected):
    assert detect_alphabet(seq) is expected


def test_detect_alphabet_empty_raises():
    with pytest.raises(SequenceError):
        detect_alphabet("   ")


def test_reverse_complement_dna():
    assert reverse_complement("ATGC", SequenceAlphabet.DNA) == "GCAT"


def test_reverse_complement_rna():
    assert reverse_complement("AUGC", SequenceAlphabet.RNA) == "GCAU"


def test_reverse_complement_ambiguity_codes():
    # R<->Y, full palindromic check on a mixed code string.
    assert reverse_complement("RYSWKM", SequenceAlphabet.DNA) == "KMWSRY"


def test_reverse_complement_protein_rejected():
    with pytest.raises(SequenceError):
        reverse_complement("MKLV", SequenceAlphabet.PROTEIN)


def test_is_ambiguous():
    assert is_ambiguous("ACGTN", SequenceAlphabet.DNA) is True
    assert is_ambiguous("ACGT", SequenceAlphabet.DNA) is False


def test_validate_sequence_rejects_illegal_chars():
    with pytest.raises(SequenceError):
        validate_sequence("ACGTZ", SequenceAlphabet.DNA)


def test_validate_sequence_ambiguity_gate():
    assert validate_sequence("ACGTN", SequenceAlphabet.DNA).seq == "ACGTN"
    with pytest.raises(SequenceError):
        validate_sequence("ACGTN", SequenceAlphabet.DNA, allow_ambiguous=False)


def test_validate_sequence_autodetects():
    bs = validate_sequence("acgu")
    assert bs.alphabet is SequenceAlphabet.RNA
    assert bs.seq == "ACGU"


def test_biological_sequence_rejects_empty():
    with pytest.raises(ValueError):
        BiologicalSequence(seq="   ", alphabet=SequenceAlphabet.DNA)


def test_parse_fasta_multi_record():
    text = ">seq1 human\nACGT\nACGT\n>seq2\nMKLV\n"
    recs = parse_fasta(text)
    assert [r.seq_id for r in recs] == ["seq1 human", "seq2"]
    assert recs[0].seq == "ACGTACGT"
    assert recs[0].alphabet is SequenceAlphabet.DNA
    assert recs[1].alphabet is SequenceAlphabet.PROTEIN


def test_parse_fasta_body_before_header_raises():
    with pytest.raises(SequenceError):
        parse_fasta("ACGT\n>seq1\nACGT\n")


def test_parse_fasta_empty_raises():
    with pytest.raises(SequenceError):
        parse_fasta("\n\n")
