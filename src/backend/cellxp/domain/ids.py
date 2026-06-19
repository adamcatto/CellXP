"""Stable, opaque, globally-unique identifiers for provenance entities.

IDs are generated at creation and never reused (`provenance_model.md` §5). The target is a
time-orderable ULID/UUIDv7; until that lands we use UUIDv4 behind this single factory so
the generation strategy can be swapped in one place.
"""

from __future__ import annotations

import uuid


def new_id() -> str:
    """Return a fresh globally-unique identifier string."""
    return str(uuid.uuid4())
