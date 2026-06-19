import json

from evals.run_evals import main, validate_catalog


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
