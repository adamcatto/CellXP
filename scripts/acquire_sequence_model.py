#!/usr/bin/env python3
"""Acquire sequence-model artifacts and reject bytes that do not match the pinned manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path


def acquire(manifest_path: Path, destination: Path) -> list[Path]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    acquired: list[Path] = []
    for artifact in manifest["weights"]:
        target = destination / artifact["filename"]
        if target.exists() and digest(target) == artifact["sha256"]:
            acquired.append(target)
            continue
        fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=destination)
        os.close(fd)
        temporary = Path(temporary_name)
        try:
            with urllib.request.urlopen(artifact["url"]) as response, temporary.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    out.write(chunk)
            observed = digest(temporary)
            if observed != artifact["sha256"]:
                raise ValueError(
                    f"checksum mismatch for {artifact['filename']}: "
                    f"expected {artifact['sha256']}, observed {observed}"
                )
            temporary.replace(target)
            acquired.append(target)
        finally:
            temporary.unlink(missing_ok=True)
    return acquired


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    for path in acquire(args.manifest, args.destination):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
