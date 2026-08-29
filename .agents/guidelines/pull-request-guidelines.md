# Descriptive Pull Requests

Every pull request must let a reviewer understand the outcome, evidence, and remaining risk without
reconstructing the work from commits or an agent transcript. This applies to agents and humans.

## Required content

Use the repository PR template and keep it current as the branch changes. Include:

1. **Outcome and motivation** — what user/developer problem the PR solves and why the chosen approach
   fits the product.
2. **Implementation** — the important behavior, architecture, contracts, migrations, configuration,
   and data/safety implications. Distinguish implemented behavior from selected or planned work.
3. **Review guide** — point reviewers to the highest-value files, flows, and design decisions rather
   than listing every touched file.
4. **Visual evidence** — for user-visible work, attach relevant Playwright screenshots or a short
   recording. Explain what each image demonstrates. Prefer deterministic fixtures and redact private
   data. If visuals are not applicable, say why.
5. **Verification** — list exact commands and results: pass counts, skips/deselections, build/type/
   lint status, and any hardware/service profile used. Do not write only “tests pass.”
6. **Interpretation** — explain what the results establish, known baseline failures, and why any
   failure is unrelated or accepted. Never hide, relabel, or silently omit a failing check.
7. **Limitations and follow-ups** — identify intentionally deferred work, rollout/compatibility risk,
   and what remains behind a feature flag or evaluation gate.
8. **Documentation and planning** — name the contracts, ADRs, roadmap, guides, and changelog entries
   updated; explicitly note genuinely unaffected categories when relevant.

## Screenshots and artifacts

- Embed screenshots near the feature or claim they support, with a short caption.
- Use the final tested UI and viewport, not an obsolete intermediate state.
- Prefer Playwright-generated captures checked into an appropriate documentation asset directory or
  uploaded as PR artifacts.
- Include before/after views when the value is comparative.
- Do not attach raw biological/private inputs, secrets, internal URLs, or unredacted logs.
- For backend-only work, a compact protocol trace, architecture diagram, or test report may be more
  useful than a screenshot.

## Test reporting examples

Good:

```text
- `python -m pytest -q tests/unit/test_harness_skills.py` — 5 passed
- `pnpm --dir src/frontend test:browser` — 7 passed, 4 documented opt-in tests skipped
- Full mypy still reports 3 pre-existing errors in X/Y; focused package mypy is clean.
```

Avoid:

```text
- Tests pass
- Lint mostly clean
```

## Maintenance rule

Create or update the draft PR after the first pushed implementation and after every meaningful
follow-up. Before handoff, reconcile the title/body with the final diff and latest verification;
remove stale claims and superseded test counts. Keep the body concise enough to scan, but never gain
brevity by dropping evidence, caveats, or interpretation.

## Related

`.github/PULL_REQUEST_TEMPLATE.md` · `.agents/guidelines/feature-documentation.md` ·
`.agents/guidelines/testing.md` · `.agents/guidelines/atomic-commits.md`
