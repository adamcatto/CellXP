"""Unit tests for the variant_effect subgraph (N5, FR-13, FR-24).

Tests the full pipeline using injectable mock services so no real model backends are
needed. Covers: mammalian and prokaryote routing, binding delta, no-variant guard,
validation failure, Steps/evidence on all paths (FR-24 run-trace compliance).
"""

from __future__ import annotations

from typing import Any

import pytest

from cellxp.agent.nodes.evidence_integrator import run as evidence_integrator_run
from cellxp.agent.state import (
    AgentState,
    ExecutionCursor,
    NormalizedInputs,
    Plan,
    Subtask,
)
from cellxp.agent.subgraphs.variant_effect import build_subgraph
from cellxp.domain.enums import ConfidenceBand, OrganismClass, PlanKind, SubtaskType, TaskStatus
from cellxp.domain.evidence import Confidence
from cellxp.domain.models import Variant
from cellxp.services.alphagenome.client import AlphaGenomeService
from cellxp.services.alphagenome.schemas import (
    AssayDelta,
    VariantEffect,
    VariantEffectRequest,
    VariantEffectResult,
)
from cellxp.services.base import ServiceOutcome
from cellxp.services.binding.delta import BindingDelta, BindingDeltaRequest, BindingDeltaResult
from cellxp.services.binding.service import BindingService
from cellxp.services.reference.genome import ReferenceGenomeService


# ---------------------------------------------------------------------------
# Mock model backends
# ---------------------------------------------------------------------------


class _MockAlphaBackend:
    def score_variants(self, request: VariantEffectRequest) -> VariantEffectResult:
        effects = [
            VariantEffect(
                variant_id=f"{v.chrom}:{v.pos + 1}:{v.ref}>{v.alt}",
                deltas=[AssayDelta(assay="DNASE", value=-0.3, direction="down")],
                top_effects=[AssayDelta(assay="DNASE", value=-0.3, direction="down")],
                confidence=Confidence(band=ConfidenceBand.MEDIUM, score=0.7),
            )
            for v in request.variants
        ]
        return VariantEffectResult(per_variant=effects)

    def score_sequences(self, req):  # noqa: ANN001
        ...

    def predict_tracks(self, req):  # noqa: ANN001
        ...

    def score_splicing(self, req):  # noqa: ANN001
        ...


class _MockBindingBackend:
    def score_delta(self, request: BindingDeltaRequest) -> BindingDeltaResult:
        return BindingDeltaResult(
            deltas=[BindingDelta(tf="GATA1", value=-0.5, direction="loss")],
            confidence=Confidence(band=ConfidenceBand.MEDIUM),
        )


# ---------------------------------------------------------------------------
# AgentState builder helpers
# ---------------------------------------------------------------------------


def _make_subtask(type_: SubtaskType = SubtaskType.VARIANT_EFFECT) -> Subtask:
    return Subtask(type=type_, capability="variant_effect", status=TaskStatus.RUNNING)


def _state_with_variant(
    variant: Variant,
    organism: str = "Homo sapiens",
    assembly: str = "GRCh38",
    subtask: Subtask | None = None,
) -> AgentState:
    sub = subtask or _make_subtask()
    cursor = ExecutionCursor(active_subtask_id=sub.id)
    inputs = NormalizedInputs(organism=organism, assembly=assembly, variants=[variant])
    return AgentState(
        user_query="what does this variant do?",
        subtasks=[sub.model_dump()],
        cursor=cursor.model_dump(),
        normalized_inputs=inputs.model_dump(),
        evidence=[],
        artifacts=[],
        steps=[],
        errors=[],
    )


def _human_variant() -> Variant:
    return Variant(chrom="chr1", pos=999, ref="A", alt="T", assembly="GRCh38")


def _ecoli_variant() -> Variant:
    return Variant(chrom="NC_000913.3", pos=500_000, ref="G", alt="C",
                   assembly="GCF_000005845.2")


# ---------------------------------------------------------------------------
# Subgraph with no backends (development mode)
# ---------------------------------------------------------------------------


class TestSubgraphNoBacked:
    def _node(self) -> Any:
        return build_subgraph()

    def test_human_variant_completes_without_backend(self):
        node = self._node()
        state = _state_with_variant(_human_variant())
        result = node(state)
        subtasks = [Subtask.model_validate(s) for s in result["subtasks"]]
        active = subtasks[0]
        # UNSUPPORTED from AlphaGenome is a non-error path; subtask still completes.
        assert active.status is TaskStatus.DONE

    def test_steps_emitted_without_backend(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        assert len(result.get("steps", [])) >= 2  # extract_variant_context + call_effect_oracle

    def test_no_variants_in_state_fails_subtask(self):
        node = self._node()
        sub = _make_subtask()
        cursor = ExecutionCursor(active_subtask_id=sub.id)
        state = AgentState(
            subtasks=[sub.model_dump()],
            cursor=cursor.model_dump(),
            normalized_inputs=NormalizedInputs().model_dump(),
            evidence=[],
            artifacts=[],
            steps=[],
            errors=[],
        )
        result = node(state)
        subtasks = [Subtask.model_validate(s) for s in result["subtasks"]]
        assert subtasks[0].status is TaskStatus.FAILED
        assert result.get("errors")

    def test_no_active_subtask_returns_empty(self):
        node = self._node()
        state = AgentState(
            subtasks=[],
            cursor=ExecutionCursor().model_dump(),
            normalized_inputs=NormalizedInputs().model_dump(),
        )
        assert node(state) == {}


# ---------------------------------------------------------------------------
# Subgraph with mock AlphaGenome backend
# ---------------------------------------------------------------------------


class TestSubgraphWithAlphaBackend:
    def _node(self) -> Any:
        return build_subgraph(
            alphagenome_service=AlphaGenomeService(model_backend=_MockAlphaBackend()),
        )

    def test_human_variant_produces_ok(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        subtasks = [Subtask.model_validate(s) for s in result["subtasks"]]
        assert subtasks[0].status is TaskStatus.DONE

    def test_evidence_items_emitted(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        assert len(result.get("evidence", [])) >= 1

    def test_steps_have_call_effect_oracle(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        step_names = [s.name if hasattr(s, "name") else s["name"] for s in result["steps"]]
        assert "call_effect_oracle" in step_names

    def test_extract_variant_context_step_present(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        step_names = [s.name if hasattr(s, "name") else s["name"] for s in result["steps"]]
        assert "extract_variant_context" in step_names

    def test_ecoli_alpha_not_applicable_returns_unsupported_oracle_step(self):
        node = self._node()
        result = node(_state_with_variant(
            _ecoli_variant(), organism="Escherichia coli", assembly="GCF_000005845.2"
        ))
        # Oracle UNSUPPORTED is non-error; subtask still done.
        subtasks = [Subtask.model_validate(s) for s in result["subtasks"]]
        assert subtasks[0].status is TaskStatus.DONE


# ---------------------------------------------------------------------------
# Subgraph with mock AlphaGenome + Binding backends
# ---------------------------------------------------------------------------


class TestSubgraphWithBindingBackend:
    def _node(self) -> Any:
        return build_subgraph(
            alphagenome_service=AlphaGenomeService(model_backend=_MockAlphaBackend()),
            binding_service=BindingService(binding_backend=_MockBindingBackend()),
        )

    def test_binding_delta_step_emitted_for_human(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        step_names = [s.name if hasattr(s, "name") else s["name"] for s in result["steps"]]
        assert "compute_binding_delta" in step_names

    def test_binding_delta_evidence_emitted(self):
        node = self._node()
        result = node(_state_with_variant(_human_variant()))
        evidence = result.get("evidence", [])
        assert len(evidence) >= 1

    def test_binding_delta_not_emitted_for_ecoli(self):
        node = self._node()
        result = node(_state_with_variant(
            _ecoli_variant(), organism="Escherichia coli", assembly="GCF_000005845.2"
        ))
        step_names = [s.name if hasattr(s, "name") else s["name"] for s in result["steps"]]
        assert "compute_binding_delta" not in step_names


# ---------------------------------------------------------------------------
# Validation path: reference service rejects variant
# ---------------------------------------------------------------------------


class TestSubgraphValidationFailure:
    def test_out_of_bounds_variant_fails_subtask(self):
        node = build_subgraph(
            alphagenome_service=AlphaGenomeService(model_backend=_MockAlphaBackend()),
        )
        # chr22 length is 50_818_468; pos 60_000_000 is out of bounds.
        bad_variant = Variant(chrom="chr22", pos=60_000_000, ref="A", alt="T")
        result = node(_state_with_variant(bad_variant))
        subtasks = [Subtask.model_validate(s) for s in result["subtasks"]]
        assert subtasks[0].status is TaskStatus.FAILED
        assert result.get("errors")


# ---------------------------------------------------------------------------
# Evidence integrator
# ---------------------------------------------------------------------------


class TestEvidenceIntegrator:
    def test_integrator_emits_step(self):
        sub = _make_subtask()
        cursor = ExecutionCursor(active_subtask_id=sub.id)
        state = AgentState(
            subtasks=[sub.model_dump()],
            cursor=cursor.model_dump(),
            evidence=[],
            steps=[],
        )
        result = evidence_integrator_run(state)
        assert len(result.get("steps", [])) >= 1

    def test_integration_step_is_done(self):
        sub = _make_subtask()
        cursor = ExecutionCursor(active_subtask_id=sub.id)
        state = AgentState(
            subtasks=[sub.model_dump()],
            cursor=cursor.model_dump(),
            evidence=[],
            steps=[],
        )
        result = evidence_integrator_run(state)
        from cellxp.agent.state import Step
        step = Step.model_validate(result["steps"][0])
        assert step.status is TaskStatus.DONE
        assert step.name == "evidence_integration"

    def test_integrator_pass_through_no_evidence(self):
        state = AgentState(
            subtasks=[],
            cursor=ExecutionCursor().model_dump(),
            evidence=[],
            steps=[],
        )
        result = evidence_integrator_run(state)
        # Should complete without errors.
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# FR-24: run-trace completeness — every substantive step is recorded
# ---------------------------------------------------------------------------


class TestRunTraceCompleteness:
    """Every path through the subgraph must produce at least one named Step."""

    def test_successful_human_path_steps(self):
        node = build_subgraph(
            alphagenome_service=AlphaGenomeService(model_backend=_MockAlphaBackend()),
            binding_service=BindingService(binding_backend=_MockBindingBackend()),
        )
        result = node(_state_with_variant(_human_variant()))
        assert len(result.get("steps", [])) >= 3  # context + oracle + binding

    def test_no_backend_path_still_records_steps(self):
        node = build_subgraph()
        result = node(_state_with_variant(_human_variant()))
        assert len(result.get("steps", [])) >= 2

    def test_failure_path_records_steps(self):
        node = build_subgraph()
        sub = _make_subtask()
        cursor = ExecutionCursor(active_subtask_id=sub.id)
        state = AgentState(
            subtasks=[sub.model_dump()],
            cursor=cursor.model_dump(),
            normalized_inputs=NormalizedInputs().model_dump(),
            evidence=[], artifacts=[], steps=[], errors=[],
        )
        result = node(state)
        assert len(result.get("steps", [])) >= 1
