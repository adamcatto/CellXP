"""Object store — where large/opaque payloads live (`specs/data/object_storage.md`).

Postgres holds only metadata + the object *key* (`relational_schema.md`); structures, track
arrays, plot data, figures, and uploads live here. The backend is pluggable behind the
`ObjectStore` Protocol (`OBJECT_STORE_URL`: `file://` dev → S3-compatible prod), so the
agent/services depend only on the Protocol, never a concrete vendor (`NFR-11`).

Default keys are **content-addressed** (`cas/<sha256>`) so identical payloads dedupe and any
read can verify integrity (`provenance_model.md` §6). Objects are immutable: a new result is a
new key, never an overwrite (OS-4). A read whose bytes don't hash to the stored key raises
`IntegrityError` (OS-3 / PROV-4).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable
from urllib.parse import urlparse

from pydantic import BaseModel

from cellxp.domain.errors import IntegrityError

CAS_PREFIX = "cas"


class ObjectRef(BaseModel):
    """Pointer to a stored object — what a `Step`/`ArtifactRef` persists, not the bytes."""

    key: str
    content_type: str
    size: int
    hash: str  # sha256, hex


def content_hash(data: bytes) -> str:
    """sha256 hex digest used for content addressing + integrity (`provenance_model.md` §6)."""
    return hashlib.sha256(data).hexdigest()


def cas_key(data: bytes) -> str:
    """Content-addressed key for `data`: `cas/<sha256>` (OS-2, identical bytes → same key)."""
    return f"{CAS_PREFIX}/{content_hash(data)}"


@runtime_checkable
class ObjectStore(Protocol):
    """Backend-agnostic object-store contract (`object_storage.md` §2).

    Implementations: `FilesystemObjectStore` (`file://`, dev/local-first) and an
    S3-compatible store (prod). Callers depend only on this Protocol.
    """

    def put(self, data: bytes, *, content_type: str, key: str | None = None) -> ObjectRef: ...
    def get(self, key: str) -> bytes: ...
    def open(self, key: str) -> BinaryIO: ...  # streaming for large blobs
    def exists(self, key: str) -> bool: ...
    def url(self, key: str, *, expires_s: int | None = None) -> str: ...
    def delete(self, key: str) -> None: ...  # session-deletion path only


class FilesystemObjectStore:
    """`file://` backend: content-addressed payloads under a local root (dev/local-first).

    Layout mirrors `object_storage.md` §4 — payloads live at `<root>/cas/<sha256>`; an explicit
    `key` (e.g. a `runs/<run_id>/…` alias) writes the same bytes at that path. Writes are
    integrity-checked on read: `get()` re-hashes content-addressed objects and raises
    `IntegrityError` on mismatch (PROV-4).
    """

    def __init__(self, root: str | Path) -> None:
        # Accept a bare path or a file:// URL (the OBJECT_STORE_URL form).
        if isinstance(root, str) and root.startswith("file://"):
            root = urlparse(root).path
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Keys are opaque, store-relative; reject traversal out of the root.
        p = (self.root / key).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError(f"object key escapes store root: {key!r}")
        return p

    def put(self, data: bytes, *, content_type: str, key: str | None = None) -> ObjectRef:
        digest = content_hash(data)
        key = key or f"{CAS_PREFIX}/{digest}"
        path = self._path(key)
        # Immutability (OS-4): a content-addressed key that already exists holds identical bytes
        # by construction, so writing is a no-op; an explicit key must not change content.
        if path.exists():
            if path.read_bytes() != data:
                raise IntegrityError(
                    f"refusing to overwrite immutable object with different content: {key!r}",
                    key=key,
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return ObjectRef(key=key, content_type=content_type, size=len(data), hash=digest)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise KeyError(f"no object at key {key!r}")
        data = path.read_bytes()
        self._verify(key, data)
        return data

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        if not path.exists():
            raise KeyError(f"no object at key {key!r}")
        return path.open("rb")

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def url(self, key: str, *, expires_s: int | None = None) -> str:
        """Local `file://` URL. Prod backends issue short-lived signed URLs (`object_storage.md`
        §5); access control is enforced at the API, never by guessing paths."""
        if not self.exists(key):
            raise KeyError(f"no object at key {key!r}")
        return self._path(key).as_uri()

    def delete(self, key: str) -> None:
        """Session/run-deletion path only (`provenance_model.md` §8); an audited event."""
        self._path(key).unlink(missing_ok=True)

    def _verify(self, key: str, data: bytes) -> None:
        # Content-addressed objects carry their hash in the key; verify it on read (OS-3).
        if key.startswith(f"{CAS_PREFIX}/"):
            expected = key.split("/", 1)[1]
            actual = content_hash(data)
            if actual != expected:
                raise IntegrityError(
                    f"content hash mismatch for {key!r}: stored {expected}, got {actual}",
                    key=key,
                )


def object_store_from_url(url: str) -> ObjectStore:
    """Construct the configured backend from `OBJECT_STORE_URL` (`object_storage.md` §7).

    Only `file://` is wired today; S3-compatible (`s3://`, `https://…`) is the prod backend and
    raises `NotImplementedError` until added, so misconfiguration fails loudly.
    """
    scheme = urlparse(url).scheme or "file"
    if scheme == "file":
        return FilesystemObjectStore(url)
    raise NotImplementedError(f"object store backend {scheme!r} not yet supported: {url!r}")


# Keep mypy/readers honest: the concrete store satisfies the Protocol.
_: type[ObjectStore] = FilesystemObjectStore
