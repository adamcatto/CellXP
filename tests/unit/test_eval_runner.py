import json

from evals.run_evals import evaluate_results, main, score_expected_shape, validate_catalog


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
