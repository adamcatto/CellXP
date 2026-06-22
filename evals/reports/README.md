# Release-gate reports

`evals.release_gates` evaluates the quantitative M1–M3 criteria in
`specs/planning/milestones.md`. It is fail-closed: missing evidence is `blocked`, an observed value
outside its threshold is `failed`, and only complete passing evidence is `passed`.
The biology manifest must include `biology.overall_bcr` (≥ 75%) in addition to the per-capability
thresholds. M4 thresholds are reported under `future_milestones.M4` as readiness only; its status is
always `not_started`, and this report never authorizes starting M4 before M1-M3 pass.

Run a gate from an evidence manifest:

```bash
make release-gates \
  EVIDENCE=evals/reports/m1-m3-evidence-2026-06-22.json \
  OUTPUT=evals/reports/m1-m3-gate-report-2026-06-22.json
```

Exit status is `0` for pass, `1` for a measured failure, and `2` for blocked/missing evidence. The
evidence manifest contains nested `biology`, `safety`, `trust`, `reliability`, `regressions`, and
`acceptance` measurements. Measurements must come from scored golden runs, authorized private
safety evaluation, deployed-stack telemetry, and acceptance execution; unit-test success is not a
substitute for those release measurements.

Capture real deployed API runs in a new, non-overwritable archive before scoring:

```bash
CELLXP_BUILD_REVISION="$(git rev-parse HEAD)" \
python evals/run_evals.py dispatch \
  --api-base-url http://localhost:8000/api/v1 \
  --archive-dir evals/reports/runs/staging-2026-06-22T120000Z
```

`manifest.json` hashes the exact catalogs and `results.jsonl`. The archive records dispatch errors
instead of substituting fixture output. Keep private hazard prompts and domain-review material in
their authorized store; only approved aggregate measurements belong in the evidence manifest.
