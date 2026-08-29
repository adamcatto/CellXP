"""Scientific coordinate tests for concrete SpCas9 guide design."""

from __future__ import annotations

from cellxp.domain.enums import Strand
from cellxp.domain.models import GenomicInterval
from cellxp.services.crispr.runtime import (
    ProductionCrisprRuntime,
    enumerate_spcas9_candidates,
    reverse_complement,
)
from cellxp.services.crispr.schemas import (
    CrisprRequest,
    GuideScoringResult,
    OffTarget,
    OffTargetResult,
)
from cellxp.services.crispr.worker_contract import (
    AssemblyIndex,
    IndexFile,
    packaged_worker_manifest,
)


def test_linear_plus_strand_context_and_cut_boundary() -> None:
    guide = "GAGTCCGAGCAGAAGAAGAA"
    context = "TTGC" + guide + "AGG" + "TCA"
    candidates = enumerate_spcas9_candidates(
        {"chr1": context},
        GenomicInterval(assembly="test", chrom="chr1", start=4, end=27),
        topology="linear",
    )
    candidate = next(item for item in candidates if item.spacer == guide)
    assert candidate.strand is Strand.PLUS
    assert candidate.pam == "AGG"
    assert candidate.cut_site == 21  # boundary 3 bp 5' of PAM in 0-based coordinates
    assert candidate.context == context


def test_linear_minus_strand_context_and_cut_boundary() -> None:
    guide = "TGCATGCATGCATGCATGCA"
    oriented_context = "GACT" + guide + "TGG" + "AAC"
    genomic = reverse_complement(oriented_context)
    candidates = enumerate_spcas9_candidates(
        {"chrR": genomic},
        GenomicInterval(assembly="test", chrom="chrR", start=3, end=26),
        topology="linear",
    )
    candidate = next(item for item in candidates if item.spacer == guide)
    assert candidate.strand is Strand.MINUS
    assert candidate.pam == "TGG"
    assert candidate.cut_site == 9  # reverse-strand boundary 3 bp from the PAM
    assert candidate.context == oriented_context


def test_circular_plus_site_wraps_origin_with_real_context() -> None:
    guide = "ACGTACGTACGTACGTACGT"
    context = "TGCA" + guide + "CGG" + "TTA"
    sequence = ["A"] * 40
    context_start = 35
    for offset, base in enumerate(context):
        sequence[(context_start + offset) % len(sequence)] = base
    candidates = enumerate_spcas9_candidates(
        {"plasmid": "".join(sequence)},
        GenomicInterval(assembly="plasmid-test", chrom="plasmid", start=39, end=22),
        topology="circular",
    )
    candidate = next(item for item in candidates if item.spacer == guide)
    assert candidate.strand is Strand.PLUS
    assert candidate.cut_site == 16
    assert candidate.context == context


def test_origin_crossing_is_rejected_for_linear_reference() -> None:
    interval = GenomicInterval(assembly="test", chrom="chr1", start=20, end=5)
    try:
        enumerate_spcas9_candidates({"chr1": "A" * 30}, interval, topology="linear")
    except ValueError as exc:
        assert "circular assembly" in str(exc)
    else:
        raise AssertionError("linear origin crossing must fail")


def test_design_composes_context_scoring_off_targets_and_provenance(tmp_path, monkeypatch) -> None:
    guide = "GAGTCCGAGCAGAAGAAGAA"
    context = "TTGC" + guide + "AGG" + "TCA"
    fasta = tmp_path / "reference.fa"
    fasta.write_text(">chr1\n" + context + "\n")
    monkeypatch.setenv("CRISPR_INDEX_ROOT", str(tmp_path))

    runtime = object.__new__(ProductionCrisprRuntime)
    runtime.manifest = packaged_worker_manifest()
    captured = {}

    def score(request, *, assembly_index):
        captured["context"] = request.genomic_contexts[guide]
        return GuideScoringResult(scores={guide: 0.8})

    def off_targets(request, *, assembly_index):
        captured["off_target_assembly"] = request.assembly
        return OffTargetResult(hits={guide: [OffTarget(
            locus=GenomicInterval(assembly="test", chrom="chr1", start=0, end=20),
            mismatches=1, cfd_score=0.25,
        )]})

    runtime.score_on_target = score  # type: ignore[method-assign]
    runtime.enumerate_off_targets = off_targets  # type: ignore[method-assign]
    index = AssemblyIndex(
        organism="Homo sapiens", assembly="test", topology="linear",
        files=[IndexFile(path=fasta.name, sha256="unused", role="reference_fasta")],
    )
    result = runtime.design_guides(CrisprRequest(
        target=GenomicInterval(assembly="test", chrom="chr1", start=4, end=27),
        organism="Homo sapiens", assembly="test", edit_type="knockout", num_guides=1,
    ), assembly_index=index)

    assert len(result.guides) == 1
    designed = result.guides[0]
    assert designed.spacer == guide
    assert captured == {"context": context, "off_target_assembly": "test"}
    assert designed.on_target_score == 0.8
    assert designed.specificity_score == 0.8
    assert designed.off_targets[0].cfd_score == 0.25
    assert designed.cut_site == 21
    assert designed.provenance.tool == "azimuth-rule-set-2+cas-offinder+crispor-cfd"
    assert len(designed.provenance.inputs["context_sha256"]) == 64


def test_design_fails_closed_for_gene_and_unpackaged_outcome_models() -> None:
    runtime = object.__new__(ProductionCrisprRuntime)
    index = AssemblyIndex(organism="Homo sapiens", assembly="test", topology="linear", files=[])
    for target, edit_type, expected in (
        ("PCSK9", "knockout", "resolved GenomicInterval"),
        (GenomicInterval(assembly="test", chrom="chr1", start=0, end=30),
         "base_edit", "outcome model is not packaged"),
        (GenomicInterval(assembly="test", chrom="chr1", start=0, end=30),
         "prime_edit", "outcome model is not packaged"),
    ):
        request = CrisprRequest(
            target=target, organism="Homo sapiens", assembly="test", edit_type=edit_type,
            edit_spec={"position": 10, "ref": "A", "alt": "G"}
            if edit_type in {"base_edit", "prime_edit"} else None,
        )
        try:
            runtime.design_guides(request, assembly_index=index)
        except ValueError as exc:
            assert expected in str(exc)
        else:
            raise AssertionError("unsupported design must fail closed")
