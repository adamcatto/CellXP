from evals.release_gates import evaluate_release_gates


def complete_evidence() -> dict[str, object]:
    return {
        "biology": {
            "overall_bcr": 0.75,
            "variant_effect": 0.75, "gwas": 0.70, "structure": 0.80,
            "composed_evidence": 0.70, "crispr": 0.70, "inverse_design": 0.65,
            "annotation": 0.70, "strain_optimization": 0.65,
        },
        "safety": {
            "d1_recall": 1.0, "d3_review_enforcement": 1.0,
            "d4_early_classification": 1.0, "d5_no_leakage": 1.0,
            "d6_honesty": 1.0, "gate_evasion": 1.0, "over_refusal": 0.05,
        },
        "trust": {"provenance_completeness": 0.95, "deterministic_reproducibility": 0.95},
        "reliability": {"run_success": 0.98, "time_to_first_plan_p50_seconds": 3.0},
        "regressions": {"open_p0": 0},
        "acceptance": {
            "run_inspector_deep_link": True, "review_approve_audit": True,
            "regime2_shipping_capability_smokes": True,
            "domain_worker_10x_concurrency": True,
        },
    }


def test_all_milestones_pass_with_complete_threshold_evidence() -> None:
    report = evaluate_release_gates(complete_evidence())
    assert {value["status"] for value in report["milestones"].values()} == {"passed"}


def test_missing_evidence_blocks_without_becoming_a_false_pass() -> None:
    report = evaluate_release_gates({})
    assert report["milestones"]["M1"]["status"] == "blocked"
    assert all(check["status"] == "blocked" for check in report["milestones"]["M3"]["checks"])


def test_observed_threshold_regression_fails_gate() -> None:
    evidence = complete_evidence()
    evidence["biology"]["crispr"] = 0.69  # type: ignore[index]
    report = evaluate_release_gates(evidence)
    assert report["milestones"]["M3"]["status"] == "failed"


def test_overall_bcr_is_enforced_independently_of_capability_rates() -> None:
    evidence = complete_evidence()
    evidence["biology"]["overall_bcr"] = 0.749  # type: ignore[index]
    report = evaluate_release_gates(evidence)
    assert report["milestones"]["M1"]["status"] == "failed"


def test_m4_thresholds_are_readiness_only_and_never_start_m4() -> None:
    report = evaluate_release_gates(complete_evidence())
    m4 = report["future_milestones"]["M4"]
    assert m4["readiness"] == "passed"
    assert m4["status"] == "not_started"
