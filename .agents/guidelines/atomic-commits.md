# Atomic Commits

How agents (and humans) should stage and commit changes in this repo. Applies whenever you create
a git commit — whether at the user's request or as part of finishing a task.

## Principles

- **One logical change per commit.** A commit should represent a single, reviewable unit of work
  (one feature slice, one fix, one spec update). Split unrelated changes into separate commits.
- **Only the files you touched.** Never commit the whole working tree. List every path explicitly so
  unrelated staged or modified files cannot slip in.
- **Scoped commit message.** Use a short, imperative subject that names the scope (e.g.
  `specs: add artifact model`, `guidelines: document atomic commits`).

## When to commit

- Commit only when the user explicitly asks, or when your task instructions require it.
- Before committing, run `git status` and `git diff` to confirm exactly which files belong in this
  commit. Exclude secrets (`.env`, credentials) and unrelated WIP.

## How to commit (path-scoped)

Always pass explicit paths to `git commit` so Git records only those files.

### Tracked files (already in the repo)

Stage only the paths for this commit, then commit with path arguments:

```bash
git add "path/to/file1" "path/to/file2"
git commit -m "<scoped message>" -- path/to/file1 path/to/file2
```

If files are already staged correctly, you can skip `git add` and commit directly:

```bash
git commit -m "<scoped message>" -- path/to/file1 path/to/file2
```

### Brand-new (untracked) files

Reset the index first so nothing else is staged, then add and commit only the new paths:

```bash
git restore --staged :/ && git add "path/to/file1" "path/to/file2" && git commit -m "<scoped message>" -- path/to/file1 path/to/file2
```

Quote paths that contain spaces or special characters.

## Workflow checklist

1. `git status` — see all modified/untracked files.
2. `git diff` (and `git diff --staged` if needed) — verify the change set matches one logical unit.
3. Choose the command above (tracked vs brand-new).
4. `git status` after commit — confirm a clean or expected remaining working tree.

## Splitting mixed changes

If `git status` shows files that belong to different logical changes, make **separate atomic
commits** — one scoped command per commit, each with its own path list and message. Do not combine
unrelated spec edits, code changes, and drive-by fixes in one commit.

## Don't

- Don't run `git commit -a` or `git commit` without path arguments when other files are modified.
- Don't use `git add .` or `git add -A` unless you intend every changed file in that directory and
  have verified none are unrelated.
- Don't amend, force-push, or skip hooks unless the user explicitly requests it (see repo git
  safety rules).
- Don't commit secrets or generated artifacts that belong in `.gitignore`.

## Related

`.agents/guidelines/changelog-guidelines.md` · `CHANGELOG.md` · `CONTRIBUTING.md`
