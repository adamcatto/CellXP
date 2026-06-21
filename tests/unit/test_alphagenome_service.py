"""Unit tests for AlphaGenomeService and coordinate transforms (N5, FR-13, AGS-1..5)."""

from __future__ import annotations

import pytest

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence
from cellxp.domain.models import Variant
from cellxp.services.alphagenome.client import AlphaGenomeService
from cellxp.services.alphagenome.schemas import (
    AssayDelta,
    SequenceScoringRequest,
    SequenceScoringResult,
    SpliceEffectRequest,
    SpliceEffectResult,
    TrackPredictionRequest,
    TrackPredictionResult,
    VariantEffect,
    VariantEffectRequest,
    VariantEffectResult,
    alphagenome_applicable,
    select_oracle,
)
from cellxp.services.alphagenome.transforms import (
    compute_deltas,
    frame_sequence_window,
    pos_in_window,
    substitute_allele,
    variant_id,
)
from cellxp.services.base import ServiceOutcome
from cellxp.domain.errors import CoordinateError
from cellxp.services.reference.genome import ASSEMBLY_CATALOG


# ---------------------------------------------------------------------------
# Oracle selection (AGS-1)
# ---------------------------------------------------------------------------


class TestOracleSelection:
    def test_human_selects_alphagenome(self):
        assert select_oracle("Homo sapiens") == "alphagenome"

    def test_mouse_selects_alphagenome(self):
        assert select_oracle("Mus musculus") == "alphagenome"

    def test_ecoli_selects_evo2(self):
        assert select_oracle("Escherichia coli") == "evo2"

    def test_goxydans_selects_evo2(self):
        assert select_oracle("Gluconobacter oxydans") == "evo2"

    def test_unknown_organism_returns_unsupported(self):
        assert select_oracle("Martian") == "unsupported"

    def test_alphagenome_applicable_human(self):
        assert alphagenome_applicable("Homo sapiens") is True

    def test_alphagenome_not_applicable_ecoli(self):
        assert alphagenome_applicable("Escherichia coli") is False


# ---------------------------------------------------------------------------
# Score-variants — organism routing and no-backend path
# ---------------------------------------------------------------------------


class _MockModelBackend:
    """Minimal ModelBackend stub returning canned VariantEffectResult."""

    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        effects = [
            VariantEffect(
                variant_id=f"{v.chrom}:{v.pos + 1}:{v.ref}>{v.alt}",
                deltas=[AssayDelta(assay="DNASE", value=-0.42, direction="down")],
                top_effects=[AssayDelta(assay="DNASE", value=-0.42, direction="down")],
                confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.61),
            )
            for v in request.variants
        ]
        return VariantEffectResult(per_variant=effects)

    def score_sequences(self, request: SequenceScoringRequest) -> SequenceScoringResult:
        return SequenceScoringResult(scores=[0.5] * len(request.sequences))

    def predict_tracks(self, request: TrackPredictionRequest) -> TrackPredictionResult:
        return TrackPredictionResult(tracks={"DNASE": [0.1] * 10})

    def score_splicing(self, request: SpliceEffectRequest) -> SpliceEffectResult:
        return SpliceEffectResult(
            donor_loss=0.05,
            confidence=Confidence(band=ConfidenceBand.LOW),
        )


def _variant(chrom: str = "chr1", pos: int = 999, ref: str = "A", alt: str = "T") -> Variant:
    return Variant(chrom=chrom, pos=pos, ref=ref, alt=alt, assembly="GRCh38")


class TestScoreVariantsNoBackend:
    def test_no_backend_human_returns_unsupported(self):
        svc = AlphaGenomeService()
        result = svc.score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_no_backend_ecoli_returns_unsupported(self):
        svc = AlphaGenomeService()
        result = svc.score_variants(
            VariantEffectRequest(
                variants=[_variant()], organism="Escherichia coli", assembly="GCF_000005845.2"
            )
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_unknown_organism_returns_unsupported(self):
        svc = AlphaGenomeService()
        result = svc.score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Alien", assembly="AlienAsm")
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_result_carries_step_on_unsupported(self):
        svc = AlphaGenomeService()
        result = svc.score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        assert len(result.steps) >= 1


class TestScoreVariantsWithBackend:
    def _svc(self) -> AlphaGenomeService:
        return AlphaGenomeService(model_backend=_MockModelBackend())

    def test_human_with_backend_returns_ok(self):
        result = self._svc().score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.OK

    def test_result_contains_per_variant_effects(self):
        result = self._svc().score_variants(
            VariantEffectRequest(
                variants=[_variant("chr1", 1000, "G", "A")],
                organism="Homo sapiens",
                assembly="GRCh38",
            )
        )
        assert len(result.value.per_variant) == 1

    def test_delta_assay_present(self):
        result = self._svc().score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        effect = result.value.per_variant[0]
        assert len(effect.deltas) >= 1
        assert effect.deltas[0].assay == "DNASE"

    def test_confidence_band_present(self):
        result = self._svc().score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        effect = result.value.per_variant[0]
        assert effect.confidence.band is not None

    def test_evidence_item_emitted(self):
        result = self._svc().score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        assert len(result.evidence) >= 1

    def test_step_emitted(self):
        result = self._svc().score_variants(
            VariantEffectRequest(variants=[_variant()], organism="Homo sapiens", assembly="GRCh38")
        )
        assert len(result.steps) >= 1

    def test_ecoli_oracle_is_evo2_not_alphagenome(self):
        # select_oracle returns "evo2" for E. coli; ModelBackend is called with that oracle.
        # Oracle selection correctness is tested in TestOracleSelection; here we verify the
        # service does NOT block the call with an UNSUPPORTED result (evo2 is a valid oracle).
        svc = AlphaGenomeService(model_backend=_MockModelBackend())
        result = svc.score_variants(
            VariantEffectRequest(
                variants=[_variant()],
                organism="Escherichia coli",
                assembly="GCF_000005845.2",
            )
        )
        # The backend is called; it returns OK.  AGS-1 is satisfied: oracle == "evo2", not
        # "alphagenome", so the mammalian-only guard was never triggered.
        assert result.outcome is ServiceOutcome.OK

    def test_multiple_variants_returns_one_effect_each(self):
        result = self._svc().score_variants(
            VariantEffectRequest(
                variants=[_variant("chr1", 100), _variant("chr1", 200)],
                organism="Homo sapiens",
                assembly="GRCh38",
            )
        )
        assert len(result.value.per_variant) == 2


class TestScoreSplicing:
    def test_ecoli_returns_unsupported(self):
        svc = AlphaGenomeService(model_backend=_MockModelBackend())
        result = svc.score_splicing(
            SpliceEffectRequest(
                variant=_variant(), organism="Escherichia coli", assembly="GCF_000005845.2"
            )
        )
        assert result.outcome is ServiceOutcome.UNSUPPORTED

    def test_human_with_backend_returns_ok(self):
        svc = AlphaGenomeService(model_backend=_MockModelBackend())
        result = svc.score_splicing(
            SpliceEffectRequest(variant=_variant(), organism="Homo sapiens", assembly="GRCh38")
        )
        assert result.outcome is ServiceOutcome.OK


# ---------------------------------------------------------------------------
# Coordinate transforms
# ---------------------------------------------------------------------------


class TestFrameSequenceWindow:
    def _asm(self):
        return ASSEMBLY_CATALOG["GRCh38"]

    def test_window_centered_on_variant(self):
        v = _variant("chr1", 50000)
        start, end = frame_sequence_window(v, assembly_info=self._asm(), window_bp=1000)
        assert start == 49500
        assert end == 50500

    def test_window_clamped_at_start_of_contig(self):
        v = _variant("chr1", 100)
        start, end = frame_sequence_window(v, assembly_info=self._asm(), window_bp=1000)
        assert start == 0
        assert end == 600  # 100 + 500 = 600

    def test_window_clamped_at_end_of_contig(self):
        v = _variant("chr1", 248_956_000)
        contig_len = 248_956_422
        start, end = frame_sequence_window(v, assembly_info=self._asm(), window_bp=1000)
        assert end == contig_len
        assert start == 248_956_000 - 500

    def test_unknown_contig_raises_coordinate_error(self):
        v = _variant("chrUNKNOWN", 100)
        with pytest.raises(CoordinateError):
            frame_sequence_window(v, assembly_info=self._asm(), window_bp=100)


class TestSubstituteAllele:
    def test_snv_substitution(self):
        seq = "ACGTACGT"
        # pos 2 is 'G'; replacing with 'T' → "AC" + "T" + "TACGT" = "ACTTACGT"
        alt_seq = substitute_allele(seq, 2, "G", "T")
        assert alt_seq == "ACTTACGT"

    def test_allele_mismatch_raises(self):
        seq = "ACGT"
        with pytest.raises(CoordinateError):
            substitute_allele(seq, 0, "T", "G")  # seq[0] == "A", not "T"

    def test_out_of_range_raises(self):
        with pytest.raises(CoordinateError):
            substitute_allele("ACGT", 10, "A", "T")

    def test_window_length_preserved_after_substitution(self):
        seq = "ACGT" * 10
        alt = substitute_allele(seq, 5, "C", "T")
        assert len(alt) == len(seq)


class TestComputeDeltas:
    def test_basic_deltas(self):
        ref = [1.0, 2.0, 3.0]
        alt = [1.5, 1.8, 3.9]
        deltas = compute_deltas(ref, alt)
        assert len(deltas) == 3
        assert abs(deltas[0] - 0.5) < 1e-9
        assert abs(deltas[1] - (-0.2)) < 1e-9

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError):
            compute_deltas([1.0], [1.0, 2.0])


class TestVariantId:
    def test_format_is_chrom_1based_ref_alt(self):
        v = Variant(chrom="chr17", pos=7674220, ref="C", alt="T")
        assert variant_id(v) == "chr17:7674221:C>T"


class TestPosInWindow:
    def test_basic_offset(self):
        assert pos_in_window(1000, 900) == 100

    def test_position_before_window_raises(self):
        with pytest.raises(CoordinateError):
            pos_in_window(50, 100)
