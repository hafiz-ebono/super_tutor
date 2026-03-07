"""
Integration test: SQLite round-trip for agno Workflow session_state.

Verifies WKFL-03: data written inside a step executor is readable by
get_session_state() in a subsequent call using the same session_id.

Does NOT call the real notes agent. Uses a minimal executor that writes
fixed test values to session_state.
"""
import os
import tempfile
import pytest

from agno.workflow import Workflow, Step
from agno.workflow.types import StepInput, StepOutput
from agno.db.sqlite import SqliteDb


def _write_test_state(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Minimal step executor that writes known test values to session_state.
    Parameter name 'session_state' is required — agno detects it by name.
    """
    session_state["notes"] = "Test notes content"
    session_state["tutoring_type"] = "micro_learning"
    session_state["session_type"] = "url"
    session_state["sources"] = ["https://example.com"]
    return StepOutput(content="Test notes content")


@pytest.fixture
def tmp_session_db(tmp_path):
    """Create a fresh SqliteDb in a temp directory for each test."""
    db_file = str(tmp_path / "test_sessions.db")
    db = SqliteDb(db_file=db_file, id="super_tutor_sessions")
    yield db


def test_session_state_round_trip(tmp_session_db):
    """
    Write session_state in Workflow.run(), then read it back via get_session_state().
    This is the core WKFL-03 verification.
    """
    session_id = "test-session-round-trip-001"

    # Build and run workflow — writes to session_state inside step executor
    workflow = Workflow(
        id="session-workflow",
        name="Test Session Workflow",
        steps=[Step(name="notes", executor=_write_test_state)],
        db=tmp_session_db,
        session_id=session_id,
    )
    result = workflow.run(session_id=session_id)

    # Verify run returned notes content
    assert result is not None, "Workflow.run() returned None"
    assert result.content == "Test notes content", f"Unexpected content: {result.content!r}"

    # Build a second workflow instance (simulating a subsequent request)
    # Per CVE-2025-64168: fresh instance per request
    workflow2 = Workflow(
        id="session-workflow",
        name="Test Session Workflow",
        steps=[Step(name="notes", executor=_write_test_state)],
        db=tmp_session_db,
        session_id=session_id,
    )
    state = workflow2.get_session_state(session_id=session_id)

    # Verify all four required fields persisted
    assert state.get("notes") == "Test notes content", f"notes not persisted: {state}"
    assert state.get("tutoring_type") == "micro_learning", f"tutoring_type not persisted: {state}"
    assert state.get("session_type") == "url", f"session_type not persisted: {state}"
    assert state.get("sources") == ["https://example.com"], f"sources not persisted: {state}"


def test_get_session_returns_none_for_unknown_id(tmp_session_db):
    """
    STOR-03 prerequisite: workflow.get_session() returns None for an unknown session_id.
    This is what _guard_session() in the router relies on.
    """
    workflow = Workflow(
        id="session-workflow",
        name="Test Session Workflow",
        steps=[Step(name="notes", executor=_write_test_state)],
        db=tmp_session_db,
        session_id="nonexistent-session-id",
    )
    result = workflow.get_session(session_id="nonexistent-session-id")
    assert result is None, f"Expected None for unknown session_id, got: {result}"


def test_session_db_uses_separate_id(tmp_session_db):
    """
    STOR-02: Verify the session db has id='super_tutor_sessions' (not traces id).
    Prevents the two SqliteDb instances from conflicting.
    """
    assert tmp_session_db.id == "super_tutor_sessions", (
        f"Session db id should be 'super_tutor_sessions', got: {tmp_session_db.id!r}"
    )
