import pytest
from cellxp.api.schemas import SaveGuidePoolRequest, SessionDefaults, SessionSummary
from cellxp.storage.api_repository import ApiRepository
from cellxp.storage.database import Base, make_session_factory
from cellxp.storage.guide_pool_repository import GuidePoolConflictError, GuidePoolRepository


def _repositories(tmp_path):
    factory = make_session_factory(f"sqlite:///{tmp_path}/pools.db")
    Base.metadata.create_all(factory.kw["bind"])
    ApiRepository(factory).create_session(SessionSummary(
        id="018f0000-0000-7000-8000-000000000021", type="genome_editing", title="Edit",
        defaults=SessionDefaults(review_posture="strict"), revision=0,
        created_at="2026-06-22T00:00:00+00:00", updated_at="2026-06-22T00:00:00+00:00",
    ))
    return GuidePoolRepository(factory)


def test_guide_pool_persists_order_and_optimistic_revision(tmp_path):
    repository = _repositories(tmp_path)
    request = SaveGuidePoolRequest(
        session_id="018f0000-0000-7000-8000-000000000021", guide_ids=["g2", "g1"]
    )
    created = repository.save("018f0000-0000-7000-8000-000000000022", request)
    assert (created.guide_ids, created.revision) == (["g2", "g1"], 0)

    updated = repository.save(
        created.source_artifact_id,
        request.model_copy(update={"guide_ids": ["g1"], "expected_revision": 0}),
        pool_id=created.id,
    )
    assert (updated.guide_ids, updated.revision) == (["g1"], 1)
    listed = repository.list_for_artifact(created.source_artifact_id)
    assert [(item.id, item.guide_ids, item.revision) for item in listed] == [
        (updated.id, ["g1"], 1)
    ]

    with pytest.raises(GuidePoolConflictError, match="revision"):
        repository.save(
            created.source_artifact_id,
            request.model_copy(update={"expected_revision": 0}),
            pool_id=created.id,
        )


def test_guide_pool_rejects_duplicate_candidates():
    with pytest.raises(ValueError, match="unique"):
        SaveGuidePoolRequest(session_id="session", guide_ids=["g1", "g1"])
