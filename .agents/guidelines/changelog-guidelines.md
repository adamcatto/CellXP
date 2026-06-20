# Changelog Guidelines

How to maintain `CHANGELOG.md`. Applies to humans and agents working in this repo.

## Principles

- The changelog is **for humans**, not a raw git log. Summarize *why/what changed* at a level a user
  or contributor cares about — not every commit.
- Follow [Keep a Changelog](https://keepachangelog.com/) + [SemVer](https://semver.org/).
- There is always an **`## [Unreleased]`** section at the top; new entries go there.

## When to update

Add an entry whenever a change is user- or contributor-visible: new/changed specs or capabilities,
API/contract changes, behavior changes, removals, security fixes, notable docs. Skip purely internal
no-ops (typo fixes, formatting) unless meaningful.

> While the project is **spec-first** (pre-code), treat **new or substantially changed specs/docs as
> changelog-worthy** — that is the product surface right now.

## How to write an entry

- Put it under the right category in `[Unreleased]`: **Added / Changed / Deprecated / Removed /
  Fixed / Security**.
- Prefix every bullet with the **land date** in ISO form: `- **YYYY-MM-DD** — …`. Use the date the
  change lands on the default branch (merge day), not when work started.
- Within a category, list **newest dates first**.
- One line, imperative-ish, present tense; reference the spec/file or `FR-*`/ADR where useful.
- Be specific: "Add human-review gate spec (`specs/agent/human_review_policy.md`)" — not "update docs".
- Group related files; don't list 20 near-identical lines (e.g. "Add per-node specs
  (`specs/agent/nodes/*`)").

## Releasing a version

1. Change `## [Unreleased]` → `## [X.Y.Z] - YYYY-MM-DD` (release date on the section header); add a
   fresh empty `[Unreleased]` above it. Keep per-entry `**YYYY-MM-DD**` prefixes inside the released
   section — they record when each item landed during development.
2. Choose the bump per SemVer: **MAJOR** breaking contract change, **MINOR** new capability/spec
   (back-compatible), **PATCH** fixes/clarifications.
3. Update the link refs at the bottom (`[Unreleased]`, `[X.Y.Z]`).
4. Tag the release to match.

## Don't

- Don't dump commit messages.
- Don't leave `[Unreleased]` empty-then-release without moving entries.
- Don't record secrets, internal URLs, or credentials.

## Related

`CHANGELOG.md` · `.cursor`/repo contribution docs · ADRs in `documentation/adr/`.
