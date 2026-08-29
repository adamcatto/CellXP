"""Executable session policy tests (FR-37..39)."""

import pytest
from cellxp.domain.sessions import session_defaults


def test_genome_editing_defaults_to_strict_review():
    defaults = session_defaults("genome_editing")
    assert defaults.review_posture == "strict"
    assert "crispr" in defaults.enabled_capabilities
    assert "variant_effect" in defaults.enabled_capabilities


def test_session_defaults_are_copied_and_unknown_types_rejected():
    assert session_defaults("genome_editing") is not session_defaults("genome_editing")
    with pytest.raises(ValueError, match="unknown session type"):
        session_defaults("unknown")
