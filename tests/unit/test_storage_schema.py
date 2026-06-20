"""Relational schema structural tests (Wave 0, relational_schema.md §4, RS-4/RS-5)."""

from sqlalchemy import inspect

from cellxp.domain.enums import RunStatus
from cellxp.storage.database import make_engine, pg_enum
from cellxp.storage.models import (
    APPEND_ONLY_TABLES,
    Base,
    Run,
    WorkspaceSession,
)


def test_metadata_creates_all_history_tables():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    expected = {
        "users", "sessions", "runs", "messages", "subtasks", "steps", "evidence_items",
        "artifacts", "artifact_evidence", "clarifications", "review_items", "run_errors",
        "macros",
    }
    assert expected <= tables


def test_run_id_is_universal_fk():
    # Every child table carries a run_id FK back to runs (relational_schema.md §2).
    for table in (
        "messages", "subtasks", "steps", "evidence_items", "artifacts", "clarifications",
        "review_items", "run_errors",
    ):
        cols = Base.metadata.tables[table].c
        assert "run_id" in cols
        assert any(fk.column.table.name == "runs" for fk in cols["run_id"].foreign_keys)


def test_append_only_tables_marked():
    assert APPEND_ONLY_TABLES == frozenset(
        {"messages", "steps", "evidence_items", "artifacts", "run_errors", "audit_log"}
    )


def test_workspace_session_maps_to_sessions_table():
    assert WorkspaceSession.__tablename__ == "sessions"


def test_enum_column_stores_member_values_not_names():
    # RS-4: enum columns mirror domain/enums.py by value (e.g. "queued", not "QUEUED").
    enum_type = pg_enum(RunStatus)
    assert set(enum_type.enums) == {m.value for m in RunStatus}
    # The ORM column uses the same value-based enum.
    status_col = Run.__table__.c["status"]
    assert set(status_col.type.enums) == {m.value for m in RunStatus}
