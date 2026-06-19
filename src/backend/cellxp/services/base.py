"""Service base contract.

Every capability service (`services/README.md` "Shared contract") is a class with a unique
`name`, exposing operations that are pure functions of validated inputs to a typed
`ServiceResult[T]`. A result carries provenance (`steps`/`evidence`/`artifacts`) so the
persistence layer — never the service — writes it (`provenance_model.md`, PROV-1/2).

Three outcomes must be distinctly representable (`README.md`): a *valid empty* result
(e.g. "no motif hits"), *unsupported* (organism/assay not covered), and *failure*
(recoverable `RunError`). They are not the same thing and callers route on them differently.
"""

from __future__ import annotations

from abc import ABC
from enum import Enum
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel, Field

from cellxp.agent.state import RunError, Step
from cellxp.domain.artifacts import ArtifactRef
from cellxp.domain.evidence import EvidenceItem

T = TypeVar("T")


class ServiceOutcome(str, Enum):
    """The four representable results of a service operation."""

    OK = "ok"  # produced a value
    EMPTY = "empty"  # ran successfully, no results (distinct from unsupported/failure)
    UNSUPPORTED = "unsupported"  # organism/assay not covered — not an error
    FAILURE = "failure"  # recoverable failure carrying a RunError


class ServiceUsage(BaseModel):
    """Resource accounting fed back into the run `Budget` (`state_schema.md` §15)."""

    tokens: int | None = None
    seconds: float | None = None
    gpu_seconds: float | None = None


class ServiceResult(BaseModel, Generic[T]):
    """Typed, provenance-bearing result of a single service operation."""

    outcome: ServiceOutcome
    value: T | None = None
    error: RunError | None = None
    detail: str | None = None  # reason for an unsupported/empty result
    steps: list[Step] = Field(default_factory=list)  # >=1 per substantive call (PROV-1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    usage: ServiceUsage | None = None

    @property
    def ok(self) -> bool:
        """Whether the operation succeeded (a value or a legitimate empty result)."""
        return self.outcome in (ServiceOutcome.OK, ServiceOutcome.EMPTY)

    @classmethod
    def succeeded(
        cls,
        value: T,
        *,
        steps: list[Step] | None = None,
        evidence: list[EvidenceItem] | None = None,
        artifacts: list[ArtifactRef] | None = None,
        usage: ServiceUsage | None = None,
    ) -> ServiceResult[T]:
        return cls(
            outcome=ServiceOutcome.OK,
            value=value,
            steps=steps or [],
            evidence=evidence or [],
            artifacts=artifacts or [],
            usage=usage,
        )

    @classmethod
    def empty(
        cls, detail: str | None = None, *, steps: list[Step] | None = None
    ) -> ServiceResult[T]:
        return cls(outcome=ServiceOutcome.EMPTY, detail=detail, steps=steps or [])

    @classmethod
    def unsupported(cls, reason: str, *, steps: list[Step] | None = None) -> ServiceResult[T]:
        return cls(outcome=ServiceOutcome.UNSUPPORTED, detail=reason, steps=steps or [])

    @classmethod
    def failed(cls, error: RunError, *, steps: list[Step] | None = None) -> ServiceResult[T]:
        return cls(outcome=ServiceOutcome.FAILURE, error=error, steps=steps or [])


class Service(ABC):
    """Base class for a capability service.

    Subclasses set a unique `name` (the registry key, `services/registry.py`) and expose
    operations returning `ServiceResult`. Backend selection (in-process vs remote vendor) is
    config-only; no business logic hard-codes a vendor/endpoint (`README.md`).
    """

    name: ClassVar[str]
