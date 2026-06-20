"""X5 CRISPR service tests (FR-15, CRS-1..5)."""

from cellxp.domain.enums import ConfidenceBand
from cellxp.domain.evidence import Confidence, Provenance
from cellxp.domain.models import GenomicInterval
from cellxp.services.base import ServiceOutcome
from cellxp.services.crispr import (
    CrisprRequest, CrisprResult, CrisprService, EditOutcomeResult, Guide,
    GuideScoringResult, OffTargetResult,
)


class Backend:
    def design_guides(self, request):
        return CrisprResult(
            guides=[Guide(
                spacer="ACGTACGTACGTACGTACGT", pam="NGG", strand="+", cut_site=112,
                on_target_score=.82, specificity_score=.91,
                confidence=Confidence(band=ConfidenceBand.HIGH),
                provenance=Provenance(tool="Rule Set 2 + CFD", tool_version="test"),
            )], editing_system="SpCas9", rationale="NGG PAM available",
            storage_ref="obj://guides", off_target_storage_ref="obj://off-targets",
        )

    def enumerate_off_targets(self, request):
        return OffTargetResult(hits={guide: [] for guide in request.guides}, storage_ref="obj://ot")

    def score_on_target(self, request):
        return GuideScoringResult(scores={guide: .8 for guide in request.guides})

    def predict_edit_outcomes(self, request):
        return EditOutcomeResult(efficiencies={guide: .7 for guide in request.guides}, outcome_model="x")


def request(**updates):
    values = dict(
        target=GenomicInterval(chrom="chr1", start=100, end=200),
        organism="Homo sapiens", assembly="GRCh38", edit_type="knockout",
    )
    values.update(updates)
    return CrisprRequest(**values)


def test_design_emits_actionable_guide_and_off_target_artifacts():
    result = CrisprService(backend=Backend()).design_guides(request())
    assert result.outcome is ServiceOutcome.OK
    assert {artifact.type.value for artifact in result.artifacts} == {"guide_table", "off_target_table"}
    assert all(artifact.actionable for artifact in result.artifacts)
    assert len(result.evidence) == 1


def test_no_backend_is_explicitly_unsupported():
    assert CrisprService().design_guides(request()).outcome is ServiceOutcome.UNSUPPORTED


def test_wrong_organism_assembly_pair_is_unsupported():
    result = CrisprService(backend=Backend()).design_guides(request(assembly="GRCm39"))
    assert result.outcome is ServiceOutcome.UNSUPPORTED


def test_base_edit_requires_edit_spec():
    try:
        request(edit_type="base_edit")
    except ValueError as exc:
        assert "requires edit_spec" in str(exc)
    else:
        raise AssertionError("base-edit request accepted without edit_spec")
