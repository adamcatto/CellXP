#!/usr/bin/env python3
"""Validate a CRISPR assembly/index manifest and every referenced artifact checksum."""

from __future__ import annotations

import argparse
from pathlib import Path

from cellxp.services.crispr.worker_contract import (
    IndexManifest,
    manifest_sha256,
    verify_index_files,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    manifest = IndexManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    verify_index_files(manifest, args.manifest.parent)
    print(manifest_sha256(manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
