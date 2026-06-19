# Feature Documentation and Planning Sync

Use this checklist whenever a feature is added, changed, deprecated, or removed. A feature change is
not complete when only its implementation changes; the repository's specs, documentation, planning,
tests, and changelog must describe the same behavior.

"Feature" includes user-visible behavior and contributor-facing capabilities such as APIs, schemas,
configuration, workflows, service integrations, test infrastructure, and operational tooling.

## Required workflow

1. **Find the affected sources of truth before editing.** Follow `.agents/onboarding.md` and identify
   the relevant requirements (`FR-*`/`NFR-*`/`CR-*`), domain/service/interface specs, explanation,
   reference, planning, and contributor docs. Do not infer intended behavior from scaffold code.
2. **Update the implementation and its normative specs together.** Add or revise requirements,
   contracts, examples, diagrams, configuration and migration notes, and cross-references that the
   behavior changes. Documentation must distinguish implemented behavior from planned behavior.
3. **Synchronize planning.** Review `specs/planning/roadmap.md`, `milestones.md`, and, when relevant,
   `future-additions.md`, `open_questions.md`, and `risks.md`. Update item scope, status, dependencies,
   sequencing, or milestone when the change affects them. Put committed work on the roadmap and
   uncommitted ideas in `future-additions.md`; do not add roadmap churn for an implementation detail
   that does not change the plan.
4. **Document verification.** Add or update tests for changed behavior and document:
   - what each new test or test group covers and the requirement or regression it protects;
   - where it lives and which test tier it belongs to;
   - the exact command to run it, including required services, fixtures, environment, markers, or
     non-default hardware.

   Keep `.agents/guidelines/testing.md`, `specs/evaluation/testing_strategy.md`, regression maps, and
   contributor-facing commands accurate. Adding or changing test infrastructure is itself a feature
   change and requires this documentation sync.
5. **Update discoverability and release history.** Refresh relevant README indexes, setup/how-to/API/
   CLI/reference docs, examples, generated-contract instructions, and `CONTRIBUTING.md` extension
   points. Add a concise `[Unreleased]` entry to `CHANGELOG.md` when required by
   `changelog-guidelines.md`.
6. **Check consistency before finishing.** Search for stale names, commands, statuses, requirement
   IDs, and links. Run the applicable documentation/link checks and tests. Review the final diff as
   one coherent feature change, then follow `atomic-commits.md` if committing.

## Completion rule

The task handoff or pull-request description must list the documentation and planning files updated.
If a category above is genuinely unaffected, state that explicitly (for example, "Roadmap unchanged:
scope and delivery status did not change"). "The code is self-documenting" is not an exception.

When the implementation exposes a mismatch or missing decision in a source-of-truth spec, resolve the
spec in the same change or record the work in the appropriate planning/open-question document. Do not
silently ship behavior that contradicts the documented contract.

## Related

`.agents/onboarding.md` · `.agents/guidelines/testing.md` ·
`.agents/guidelines/changelog-guidelines.md` · `.agents/guidelines/atomic-commits.md` ·
`specs/planning/roadmap.md` · `specs/planning/future-additions.md`
