"""Time helpers.

Provenance and artifact records timestamp in **UTC ISO-8601** (`provenance_model.md` §4).
Centralizing it here keeps the format consistent and makes it trivial to freeze in tests.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string with a `+00:00` offset."""
    return datetime.now(UTC).isoformat()
