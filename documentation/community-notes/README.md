# Community Notes

Short, practical **caveats and field knowledge** that don't fit a formal spec but save everyone pain —
model gotchas, organism/assay quirks, assembly mis-features, tool conventions. Advisory by default;
if a note implies a contract change, open a spec change too.

See `CONTRIBUTING.md` → "Community notes" for the rationale and ground rules.

## Conventions

- **One note per file**, named `NNNN-short-slug.md` (zero-padded, incrementing).
- Use `TEMPLATE.md`. Every note states: **claim**, **scope** (model/organism/assay + version),
  **evidence/source** (link a run, paper, issue), **suggested action**, and **contributor + date**.
- Keep it short and specific. Prefer a concrete action over commentary.
- Set **Status**: `active` (current), `superseded` (replaced — link the successor), or `resolved`
  (folded into a spec/contract — link it).
- If a note implies dropping/adding model applicability, a coordinate convention, etc., it MUST be
  accompanied by a change to the owning spec (e.g. `specs/biology/supported_species.md`,
  `documentation/reference/external_models_and_services.md`).

## Index

| ID | Note | Scope | Status |
|---|---|---|---|
| [0001](0001-alphagenome-not-for-bacteria.md) | AlphaGenome heads don't apply to bacteria — use Evo 2 | AlphaGenome × prokaryote | active |

> Add a row when you add a note. This index is the quick-scan; the files hold the detail.

## Related

`CONTRIBUTING.md` · `specs/biology/supported_species.md` · `specs/biology/supported_assays.md` ·
`documentation/reference/external_models_and_services.md` · `specs/agent/tool_use_policy.md`.
