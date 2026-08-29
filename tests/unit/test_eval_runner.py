import json

import httpx

from evals.run_evals import (
    dispatch_api_runs,
    evaluate_results,
    main,
    score_expected_shape,
    validate_catalog,
)


def test_validate_catalog_accepts_required_shape(tmp_path):
    catalog = tmp_path / "queries.jsonl"
    catalog.write_text(
        json.dumps(
            {
                "id": "variant-001",
                "capability": "variant_effect",
                "expected": {},
                "added_at": "2026-06-19T00:00:00Z",
                "last_reviewed_at": "2026-06-19T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert validate_catalog(catalog) == []


def test_validate_catalog_reports_invalid_json_and_missing_fields(tmp_path):
    catalog = tmp_path / "queries.jsonl"
    catalog.write_text("not-json\n{}\n", encoding="utf-8")

    errors = validate_catalog(catalog)

    assert "invalid JSON" in errors[0]
    assert "missing fields" in errors[1]


def test_runner_help_is_wired(capsys):
    assert main([]) == 0
    assert "golden-query catalogs" in capsys.readouterr().out


def test_shape_scorer_checks_artifact_evidence_model_and_review() -> None:
    query = {
        "expected": {
            "required_artifacts": [{"type": "guide_table"}],
            "required_evidence_sources": ["gwas_catalog"],
            "required_models": [{"name": "alphagenome"}],
            "must_emit_review_gate": True,
        }
    }
    snapshot = {
        "artifacts": [{"type": "guide_table"}],
        "evidence": [{"source": "gwas_catalog"}],
        "steps": [{"tool": "alphagenome:2026-06"}],
        "review_emitted": True,
    }

    checks = score_expected_shape(query, snapshot)

    assert checks
    assert all(check["passed"] for check in checks)


def test_evaluate_results_fails_missing_queries(tmp_path) -> None:
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    (catalog_dir / "queries.jsonl").write_text(
        json.dumps(
            {
                "id": "variant-001", "capability": "variant_effect",
                "expected": {"required_artifacts": [{"type": "genome_track"}]},
                "added_at": "2026-06-19T00:00:00Z",
                "last_reviewed_at": "2026-06-19T00:00:00Z",
            }
        ) + "\n"
    )
    results = tmp_path / "results.jsonl"
    results.write_text("")

    report = evaluate_results(results, catalog_dir)

    assert report["failed"] == 1
    assert report["pass_rate"] == 0.0


def test_dispatch_archives_real_api_snapshots_and_refuses_overwrite(tmp_path) -> None:
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    query = {
        "id": "variant-001", "capability": "variant_effect",
        "organism": "Homo sapiens", "assembly": "GRCh38", "message": "Score rs699",
        "expected": {}, "added_at": "2026-06-19T00:00:00Z",
        "last_reviewed_at": "2026-06-19T00:00:00Z",
    }
    (catalog_dir / "queries.jsonl").write_text(json.dumps(query) + "\n")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/sessions":
            return httpx.Response(201, json={"id": "session-1"})
        if request.url.path == "/api/v1/sessions/session-1/runs":
            return httpx.Response(202, json={"run_id": "run-1"})
        return httpx.Response(
            200, json={"id": "run-1", "status": "completed", "steps": [], "evidence": []},
        )

    client = httpx.Client(
        base_url="https://cellxp.test/api/v1", transport=httpx.MockTransport(handler)
    )
    archive = tmp_path / "archive-001"
    manifest = dispatch_api_runs(
        "https://cellxp.test/api/v1", archive, catalog_dir=catalog_dir,
        poll_seconds=0, client=client,
    )

    assert manifest["dispatch_errors"] == 0
    assert manifest["results"]["sha256"]  # type: ignore[index]
    record = json.loads((archive / "results.jsonl").read_text().strip())
    assert record["run_id"] == "run-1"
    assert record["snapshot"]["status"] == "completed"
    try:
        dispatch_api_runs(
            "https://cellxp.test/api/v1", archive, catalog_dir=catalog_dir, client=client
        )
    except FileExistsError:
        pass
    else:
        raise AssertionError("dispatch archive must not be overwritten")


def test_dispatch_archives_errors_fail_closed(tmp_path) -> None:
    catalog_dir = tmp_path / "catalog"
    catalog_dir.mkdir()
    (catalog_dir / "queries.jsonl").write_text(json.dumps({
        "id": "q1", "capability": "variant_effect", "message": "query", "expected": {},
        "added_at": "2026-06-19T00:00:00Z", "last_reviewed_at": "2026-06-19T00:00:00Z",
    }) + "\n")
    client = httpx.Client(
        base_url="https://cellxp.test/api/v1",
        transport=httpx.MockTransport(lambda request: httpx.Response(503)),
    )
    archive = tmp_path / "failed-archive"
    manifest = dispatch_api_runs(
        "https://cellxp.test/api/v1", archive, catalog_dir=catalog_dir, client=client
    )
    assert manifest["dispatch_errors"] == 1
    result = json.loads((archive / "results.jsonl").read_text().strip())
    assert "snapshot" not in result
    assert result["dispatch_error"]["type"] == "HTTPStatusError"
