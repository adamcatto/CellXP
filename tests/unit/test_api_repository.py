from cellxp.api.schemas import CreateRunRequest, SessionDefaults, SessionSummary
from cellxp.storage.api_repository import ApiRepository
from cellxp.storage.database import Base, make_session_factory


def test_api_repository_survives_factory_recreation(tmp_path):
    url = f"sqlite:///{tmp_path}/runtime.db"
    factory = make_session_factory(url)
    Base.metadata.create_all(factory.kw["bind"])
    repository = ApiRepository(factory)
    summary = SessionSummary(
        id="018f0000-0000-7000-8000-000000000001", type="general", title="Durable",
        defaults=SessionDefaults(organism="human"), revision=0,
        created_at="2026-06-22T00:00:00+00:00", updated_at="2026-06-22T00:00:00+00:00",
    )
    repository.create_session(summary)
    request = CreateRunRequest(message="test", client_request_id="client-1")
    snapshot = {
        "id": "018f0000-0000-7000-8000-000000000002", "session_id": summary.id,
        "status": "queued", "created_at": "2026-06-22T00:00:01+00:00",
        "updated_at": "2026-06-22T00:00:01+00:00", "steps": [], "evidence": [],
        "artifacts": [], "errors": [],
    }
    repository.save_run(snapshot, request)

    reopened = ApiRepository(make_session_factory(url))
    assert reopened.get_session(summary.id).run_count == 1
    assert reopened.find_run(summary.id, "client-1") == snapshot["id"]
    assert reopened.runs(summary.id)[0][0]["status"] == "queued"
