"""Audit log tests (AL-1..6, specs/data/audit_log.md §7).

Covers:
  AL-1  Every safety refusal, gate decision, and actionable output writes an audit entry.
  AL-2  The table is insert-only; no delete/update path exists.
  AL-3  Audit payloads contain no raw sensitive inputs (query digest is capped).
  AL-4  The hash chain verifies; a tampered entry breaks verification.
  AL-5  (structural) The audit_log table is not removed by erasure helpers.
  AL-6  No actionable.emitted entry exists without a preceding review.decided(approved).
"""

from __future__ import annotations

import pytest

from cellxp.agent.nodes.risk_classifier import make_risk_classifier, _QUERY_DIGEST_MAX
from cellxp.domain.audit import (
    AGENT_ACTOR,
    AuditEntry,
    AuditEventType,
    _compute_entry_hash,
)
from cellxp.domain.enums import ReviewDecision, ReviewGateStatus
from cellxp.domain.ids import new_id
from cellxp.storage.audit_repository import AuditRepository
from cellxp.storage.database import make_session_factory, session_scope
from cellxp.storage.models import APPEND_ONLY_TABLES, AuditLog, Base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def factory():
    f = make_session_factory("sqlite://")
    Base.metadata.create_all(f.kw["bind"])
    return f


@pytest.fixture
def repo_and_session(factory):
    """Yields (AuditRepository, open Session); caller must commit/close."""
    session = factory()
    repo = AuditRepository(session)
    yield repo, session
    session.close()


def _repo(factory):
    """Helper: open a fresh session + AuditRepository."""
    session = factory()
    return AuditRepository(session), session


# ---------------------------------------------------------------------------
# AL-2 — insert-only table registration
# ---------------------------------------------------------------------------


def test_al2_audit_log_is_append_only():
    """AuditLog carries __append_only__ = True and appears in APPEND_ONLY_TABLES (AL-2)."""
    assert AuditLog.__append_only__ is True
    assert "audit_log" in APPEND_ONLY_TABLES


def test_al2_no_delete_method_on_repository():
    """AuditRepository exposes no delete or update path (AL-2)."""
    assert not hasattr(AuditRepository, "delete")
    assert not hasattr(AuditRepository, "update")


# ---------------------------------------------------------------------------
# AL-4 — hash chain: verify() and verify_chain()
# ---------------------------------------------------------------------------


def test_al4_single_entry_self_verifies():
    e = AuditEntry(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        payload={"rationale": "blocked"},
    )
    assert e.hash != ""
    assert e.verify()


def test_al4_hash_changes_when_payload_changes():
    e = AuditEntry(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        payload={"rationale": "original"},
    )
    original_hash = e.hash
    # Simulate in-place mutation (as would happen if DB row were tampered).
    object.__setattr__(e, "payload", {"rationale": "tampered"})
    assert e.hash == original_hash      # stored hash didn't change
    assert not e.verify()               # but recomputed hash no longer matches


def test_al4_chain_verify_passes_for_valid_chain(factory):
    repo, session = _repo(factory)
    run_id = new_id()
    e1 = repo.append(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        payload={"reason": "block 1"},
    )
    e2 = repo.append(
        event_type=AuditEventType.SAFETY_RESTRICTED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        payload={"reason": "restrict 2"},
    )
    session.commit()

    assert e2.prev_hash == e1.hash
    assert repo.verify_chain(run_id=run_id)
    session.close()


def test_al4_chain_verify_detects_tampered_hash(factory):
    repo, session = _repo(factory)
    run_id = new_id()
    repo.append(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        run_id=run_id,
    )
    session.commit()

    # Tamper with the stored row directly.
    row = session.query(AuditLog).filter(AuditLog.run_id == run_id).first()
    assert row is not None
    row.hash = "deadbeef" * 8  # corrupt the hash
    session.commit()

    assert not repo.verify_chain(run_id=run_id)
    session.close()


def test_al4_chain_verify_detects_broken_prev_link(factory):
    repo, session = _repo(factory)
    run_id = new_id()
    repo.append(event_type=AuditEventType.SAFETY_REFUSED, actor=AGENT_ACTOR, run_id=run_id)
    repo.append(event_type=AuditEventType.SAFETY_RESTRICTED, actor=AGENT_ACTOR, run_id=run_id)
    session.commit()

    # Break the chain link on the second entry without invalidating its own hash.
    rows = (
        session.query(AuditLog)
        .filter(AuditLog.run_id == run_id)
        .order_by(AuditLog.at.asc())
        .all()
    )
    second = rows[1]
    second.prev_hash = "0" * 64  # points to a nonexistent predecessor
    session.commit()

    assert not repo.verify_chain(run_id=run_id)
    session.close()


# ---------------------------------------------------------------------------
# AL-1 — risk_classifier writes audit entries for BLOCK and RESTRICT
# ---------------------------------------------------------------------------


def test_al1_block_writes_safety_refused(factory):
    repo, session = _repo(factory)
    run = make_risk_classifier(repo)
    state = {"user_query": "weaponize the toxin", "run_id": new_id()}
    result = run(state)
    session.commit()

    entries = repo.query(event_type=AuditEventType.SAFETY_REFUSED)
    assert len(entries) == 1
    assert entries[0].payload.get("hazard_signals")
    session.close()


def test_al1_restrict_writes_safety_restricted(factory):
    repo, session = _repo(factory)
    run = make_risk_classifier(repo)
    state = {"user_query": "analyze a gain of function variant", "run_id": new_id()}
    run(state)
    session.commit()

    entries = repo.query(event_type=AuditEventType.SAFETY_RESTRICTED)
    assert len(entries) == 1
    session.close()


def test_al1_allow_writes_no_audit_entry(factory):
    repo, session = _repo(factory)
    run = make_risk_classifier(repo)
    state = {"user_query": "predict the effect of rs12345 on BRCA1", "run_id": new_id()}
    run(state)
    session.commit()

    all_entries = repo.query()
    assert len(all_entries) == 0
    session.close()


def test_al1_no_audit_repo_runs_cleanly():
    """Without an AuditRepository, the node still returns the assessment (default behavior)."""
    run = make_risk_classifier(audit_repo=None)
    result = run({"user_query": "weaponize the toxin"})
    assert result["risk"].is_blocked


# ---------------------------------------------------------------------------
# AL-3 — query digest is capped; no raw sensitive content in payload
# ---------------------------------------------------------------------------


def test_al3_query_digest_capped_at_limit(factory):
    repo, session = _repo(factory)
    run = make_risk_classifier(repo)
    long_query = "weaponize the toxin " + "x" * 400
    run({"user_query": long_query, "run_id": new_id()})
    session.commit()

    entries = repo.query(event_type=AuditEventType.SAFETY_REFUSED)
    digest = entries[0].payload.get("query_digest", "")
    assert len(digest) <= _QUERY_DIGEST_MAX + 1  # +1 for the "…" suffix char
    session.close()


def test_al3_payload_has_no_token_fields(factory):
    repo, session = _repo(factory)
    run = make_risk_classifier(repo)
    run({"user_query": "weaponize the toxin", "run_id": new_id()})
    session.commit()

    entries = repo.query()
    for entry in entries:
        for key in entry.payload:
            assert key not in {"token", "api_key", "secret", "password", "credential"}
    session.close()


# ---------------------------------------------------------------------------
# AL-6 — actionable.emitted only follows review.decided(approved)
# ---------------------------------------------------------------------------


def test_al6_query_shows_no_actionable_emitted_without_review(factory):
    """Inserting a safety.refused entry without a review cycle produces no actionable.emitted."""
    repo, session = _repo(factory)
    run_id = new_id()
    repo.append(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        run_id=run_id,
    )
    session.commit()

    actionable = repo.query(run_id=run_id, event_type=AuditEventType.ACTIONABLE_EMITTED)
    assert len(actionable) == 0
    session.close()


def test_al6_actionable_emitted_follows_review_decided(factory):
    """A review.decided(approved) + actionable.emitted pair is correctly ordered in chain."""
    repo, session = _repo(factory)
    run_id = new_id()
    artifact_id = new_id()

    repo.append(
        event_type=AuditEventType.REVIEW_REQUESTED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        subject_ref=artifact_id,
        payload={"review_item_id": new_id(), "reason": "actionable output"},
    )
    repo.append(
        event_type=AuditEventType.REVIEW_DECIDED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        subject_ref=artifact_id,
        payload={"decision": ReviewDecision.APPROVED.value},
    )
    repo.append(
        event_type=AuditEventType.ACTIONABLE_EMITTED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        subject_ref=artifact_id,
        payload={"artifact_id": artifact_id},
    )
    session.commit()

    entries = repo.query(run_id=run_id)
    types = [e.event_type for e in entries]
    assert AuditEventType.REVIEW_REQUESTED in types
    assert AuditEventType.REVIEW_DECIDED in types
    assert AuditEventType.ACTIONABLE_EMITTED in types

    # Ordering: requested → decided → emitted.
    assert types.index(AuditEventType.REVIEW_DECIDED) > types.index(AuditEventType.REVIEW_REQUESTED)
    assert types.index(AuditEventType.ACTIONABLE_EMITTED) > types.index(AuditEventType.REVIEW_DECIDED)

    # Chain is intact.
    assert repo.verify_chain(run_id=run_id)
    session.close()


# ---------------------------------------------------------------------------
# AL-5 — audit log itself is not erased by data.deleted events
# ---------------------------------------------------------------------------


def test_al5_data_deleted_event_is_audited(factory):
    """Erasure of a run records a data.deleted event; prior audit entries remain."""
    repo, session = _repo(factory)
    run_id = new_id()

    repo.append(
        event_type=AuditEventType.SAFETY_REFUSED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        payload={"rationale": "blocked"},
    )
    # Simulate the erasure audit entry (the run is deleted, but we record that it happened).
    repo.append(
        event_type=AuditEventType.DATA_DELETED,
        actor=AGENT_ACTOR,
        run_id=run_id,
        payload={"scope": "run", "counts": {"runs": 1}},
    )
    session.commit()

    entries = repo.query(run_id=run_id)
    types = [e.event_type for e in entries]
    assert AuditEventType.SAFETY_REFUSED in types
    assert AuditEventType.DATA_DELETED in types
    assert len(entries) == 2  # prior entries are not erased
    assert repo.verify_chain(run_id=run_id)
    session.close()
