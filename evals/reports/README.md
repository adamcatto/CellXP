# Release-gate reports

`evals.release_gates` evaluates the quantitative M1–M3 criteria in
`specs/planning/milestones.md`. It is fail-closed: missing evidence is `blocked`, an observed value
outside its threshold is `failed`, and only complete passing evidence is `passed`.

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
