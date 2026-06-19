"""Service base + registry contract tests (Wave 0)."""

import pytest

from cellxp.agent.state import RunError, Step
from cellxp.services.base import Service, ServiceOutcome, ServiceResult
from cellxp.services.registry import ServiceRegistry


class _Dummy(Service):
    name = "dummy"


def test_register_and_get():
    reg = ServiceRegistry()
    reg.register(_Dummy)
    assert "dummy" in reg
    assert reg.get("dummy") is _Dummy
    assert reg.names() == ["dummy"]
    assert len(reg) == 1


def test_register_decorator_returns_class():
    reg = ServiceRegistry()
    assert reg.register(_Dummy) is _Dummy


def test_duplicate_registration_raises_append_only():
    reg = ServiceRegistry()
    reg.register(_Dummy)

    class _Other(Service):
        name = "dummy"  # same name

    with pytest.raises(ValueError, match="append-only"):
        reg.register(_Other)


def test_unnamed_service_rejected():
    reg = ServiceRegistry()

    class _NoName(Service):
        pass

    with pytest.raises(ValueError, match="non-empty 'name'"):
        reg.register(_NoName)


def test_get_unknown_raises():
    with pytest.raises(KeyError):
        ServiceRegistry().get("nope")


# --- ServiceResult outcomes -------------------------------------------------------------


def test_service_result_three_outcomes_are_distinct():
    ok = ServiceResult.succeeded({"hits": 3}, steps=[Step(name="scan")])
    empty = ServiceResult.empty("no motif hits")
    unsupported = ServiceResult.unsupported("AlphaGenome not applicable to prokaryotes")
    failure = ServiceResult.failed(RunError(kind="Timeout", message="upstream timeout"))

    assert ok.ok is True and ok.outcome is ServiceOutcome.OK
    assert empty.ok is True and empty.outcome is ServiceOutcome.EMPTY  # empty is success
    assert unsupported.ok is False and unsupported.outcome is ServiceOutcome.UNSUPPORTED
    assert failure.ok is False and failure.error is not None
    # empty != unsupported != failure
    assert len({empty.outcome, unsupported.outcome, failure.outcome}) == 3


def test_service_result_roundtrips_json():
    r = ServiceResult.succeeded({"x": 1}, steps=[Step(name="scan")])
    assert ServiceResult.model_validate_json(r.model_dump_json()).value == {"x": 1}
