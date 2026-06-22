"""Object-store contract tests (Wave 0, object_storage.md OS-1..OS-6, provenance_model.md §6)."""

import pytest

from cellxp.domain.errors import IntegrityError
from cellxp.storage.object_store import (
    FilesystemObjectStore,
    ObjectStore,
    S3ObjectStore,
    cas_key,
    content_hash,
    object_store_from_url,
)


@pytest.fixture
def store(tmp_path):
    return FilesystemObjectStore(tmp_path)


def test_put_returns_ref_with_hash_and_size(store):
    data = b"hello structure"
    ref = store.put(data, content_type="text/plain")
    assert ref.size == len(data)
    assert ref.hash == content_hash(data)
    assert ref.key == cas_key(data)
    assert ref.content_type == "text/plain"


def test_roundtrip_get(store):
    ref = store.put(b"PDB...", content_type="chemical/x-pdb")
    assert store.get(ref.key) == b"PDB..."
    assert store.exists(ref.key)


def test_content_addressing_dedupes_identical_bytes(store):
    a = store.put(b"same", content_type="application/json")
    b = store.put(b"same", content_type="application/json")
    assert a.key == b.key  # OS-2: identical bytes → same key


def test_distinct_bytes_distinct_keys(store):
    a = store.put(b"one", content_type="text/plain")
    b = store.put(b"two", content_type="text/plain")
    assert a.key != b.key


def test_integrity_error_on_corrupted_object(store):
    ref = store.put(b"trustworthy", content_type="text/plain")
    # Corrupt the on-disk payload behind a content-addressed key.
    path = store._path(ref.key)
    path.write_bytes(b"tampered!!!")
    with pytest.raises(IntegrityError):  # OS-3 / PROV-4
        store.get(ref.key)


def test_immutability_rejects_conflicting_overwrite(store):
    # Explicit (alias) key, then a different payload at the same key must be refused (OS-4).
    store.put(b"v1", content_type="text/plain", key="runs/r1/report.txt")
    with pytest.raises(IntegrityError):
        store.put(b"v2", content_type="text/plain", key="runs/r1/report.txt")


def test_re_put_identical_explicit_key_is_noop(store):
    ref1 = store.put(b"v1", content_type="text/plain", key="runs/r1/report.txt")
    ref2 = store.put(b"v1", content_type="text/plain", key="runs/r1/report.txt")
    assert ref1 == ref2


def test_explicit_alias_key_is_honored(store):
    ref = store.put(b"design", content_type="application/json", key="runs/r1/origami/x.json")
    assert ref.key == "runs/r1/origami/x.json"
    assert store.get(ref.key) == b"design"


def test_key_traversal_is_rejected(store):
    with pytest.raises(ValueError, match="escapes store root"):
        store.put(b"evil", content_type="text/plain", key="../../etc/passwd")


def test_get_missing_raises_keyerror(store):
    with pytest.raises(KeyError):
        store.get("cas/deadbeef")


def test_url_and_delete(store):
    ref = store.put(b"blob", content_type="text/plain")
    assert store.url(ref.key).startswith("file://")
    store.delete(ref.key)
    assert not store.exists(ref.key)


def test_open_streams_bytes(store):
    ref = store.put(b"streamed", content_type="application/octet-stream")
    with store.open(ref.key) as fh:
        assert fh.read() == b"streamed"


def test_from_url_file_scheme_builds_filesystem_store(tmp_path):
    store = object_store_from_url(f"file://{tmp_path}")
    assert isinstance(store, FilesystemObjectStore)
    assert isinstance(store, ObjectStore)  # runtime_checkable Protocol


def test_from_url_s3_scheme_builds_s3_store(monkeypatch):
    class Boto:
        @staticmethod
        def client(name, endpoint_url=None):
            return object()

    monkeypatch.setitem(__import__("sys").modules, "boto3", Boto)
    store = object_store_from_url("s3://bucket/prefix")
    assert isinstance(store, S3ObjectStore)
    assert store.bucket == "bucket"
    assert store.prefix == "prefix"


def test_from_url_unsupported_scheme_raises():
    with pytest.raises(NotImplementedError):
        object_store_from_url("ftp://bucket/prefix")
