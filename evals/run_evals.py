"""Command-line entry point for CellXP evaluation assets.

M0 only wires catalog discovery and structural validation. Executing agent runs and
rubric scoring belongs to the later T6 implementation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


CATALOG_DIR = Path(__file__).parent / "golden_queries"
REQUIRED_FIELDS = frozenset({"id", "capability", "expected", "added_at", "last_reviewed_at"})


def catalog_paths(catalog_dir: Path = CATALOG_DIR) -> list[Path]:
    """Return golden-query catalogs in deterministic order."""

    return sorted(catalog_dir.rglob("*.jsonl"))


def validate_catalog(path: Path) -> list[str]:
    """Return human-readable structural errors for one JSONL catalog."""

    errors: list[str] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{path}:{line_number}: record must be a JSON object")
            continue
        missing = sorted(REQUIRED_FIELDS - record.keys())
        if missing:
            errors.append(f"{path}:{line_number}: missing fields: {', '.join(missing)}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and validate CellXP golden-query catalogs.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("list", help="list discovered JSONL catalogs")
    subparsers.add_parser("validate", help="validate JSONL syntax and required record fields")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0

    paths = catalog_paths()
    if args.command == "list":
        for path in paths:
            print(path.relative_to(Path(__file__).parent))
        return 0

    errors = [error for path in paths for error in validate_catalog(path)]
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"Validated {len(paths)} golden-query catalog(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
