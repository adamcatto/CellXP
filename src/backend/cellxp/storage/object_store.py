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
from io import BytesIO
from typing import Any, BinaryIO, Protocol, runtime_checkable
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
        if not self.exists(key):
            raise KeyError(f"no object at key {key!r}")
        return self._path(key).as_uri()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def _verify(self, key: str, data: bytes) -> None:
        if key.startswith(f"{CAS_PREFIX}/"):
            expected = key.split("/", 1)[1]
            actual = content_hash(data)
            if actual != expected:
                raise IntegrityError(
                    f"content hash mismatch for {key!r}: stored {expected}, got {actual}",
                    key=key,
                )


class S3ObjectStore:
    """S3-compatible immutable object backend for shared regime-2/3 deployments."""

    def __init__(
        self, bucket: str, prefix: str = "", *, endpoint_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 object-store URL must include a bucket")
        if client is None:
            import boto3

            client = boto3.client("s3", endpoint_url=endpoint_url)
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, key: str) -> str:
        if key.startswith("/") or ".." in key.split("/"):
            raise ValueError(f"invalid object key: {key!r}")
        return "/".join(part for part in (self.prefix, key) if part)

    def put(self, data: bytes, *, content_type: str, key: str | None = None) -> ObjectRef:
        digest = content_hash(data)
        key = key or f"{CAS_PREFIX}/{digest}"
        remote_key = self._key(key)
        if self.exists(key):
            if self.get(key) != data:
                raise IntegrityError(f"refusing to overwrite immutable object: {key!r}", key=key)
        else:
            self.client.put_object(
                Bucket=self.bucket, Key=remote_key, Body=data, ContentType=content_type,
                Metadata={"sha256": digest},
            )
        return ObjectRef(key=key, content_type=content_type, size=len(data), hash=digest)

    def get(self, key: str) -> bytes:
        try:
            data = self.client.get_object(Bucket=self.bucket, Key=self._key(key))["Body"].read()
        except self.client.exceptions.NoSuchKey as exc:
            raise KeyError(f"no object at key {key!r}") from exc
        if key.startswith(f"{CAS_PREFIX}/") and content_hash(data) != key.split("/", 1)[1]:
            raise IntegrityError(f"content hash mismatch for {key!r}", key=key)
        return data

    def open(self, key: str) -> BinaryIO:
        return BytesIO(self.get(key))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
            return True
        except self.client.exceptions.ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise

    def url(self, key: str, *, expires_s: int | None = None) -> str:
        if not self.exists(key):
            raise KeyError(f"no object at key {key!r}")
        return self.client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": self._key(key)},
            ExpiresIn=expires_s or 900,
        )

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))


def object_store_from_url(url: str) -> ObjectStore:
    """Construct the configured backend from `OBJECT_STORE_URL` (`object_storage.md` §7).

    `s3://bucket/prefix` uses AWS configuration. `endpoint_url` supports MinIO and other
    S3-compatible services without changing callers.
    """
    scheme = urlparse(url).scheme or "file"
    if scheme == "file":
        return FilesystemObjectStore(url)
    if scheme == "s3":
        parsed = urlparse(url)
        return S3ObjectStore(parsed.netloc, parsed.path)
    raise NotImplementedError(f"object store backend {scheme!r} not yet supported: {url!r}")


# Keep mypy/readers honest: the concrete store satisfies the Protocol.
_: type[ObjectStore] = FilesystemObjectStore
