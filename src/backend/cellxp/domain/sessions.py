"""Executable session-type defaults (FR-37..39)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class SessionDefaults(BaseModel):
    type: str
    enabled_capabilities: tuple[str, ...]
    review_posture: Literal["standard", "strict"] = "standard"
    persona: str | None = None


SESSION_TYPES: dict[str, SessionDefaults] = {
    "variant_interpretation": SessionDefaults(
        type="variant_interpretation",
        enabled_capabilities=("variant_effect", "gwas", "binding", "annotation", "rag"),
        persona="researcher",
    ),
    "genome_editing": SessionDefaults(
        type="genome_editing",
        enabled_capabilities=("crispr", "variant_effect", "binding", "structure", "rag"),
        review_posture="strict",
        persona="bioengineer",
    ),
}


def session_defaults(session_type: str) -> SessionDefaults:
    try:
        return SESSION_TYPES[session_type].model_copy(deep=True)
    except KeyError:
        raise ValueError(f"unknown session type {session_type!r}") from None
