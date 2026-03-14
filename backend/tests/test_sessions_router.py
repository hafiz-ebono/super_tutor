"""
Router tests for sessions endpoints.

Tests exercise the HTTP layer without hitting real AI agents or databases.
All SQLite and background task side-effects are patched out.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.routers import sessions as sessions_router
from app.dependencies import get_traces_db


# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(sessions_router.router, prefix="/sessions")
    # Override get_traces_db so requests don't need a real SQLite connection.
    app.dependency_overrides[get_traces_db] = lambda: MagicMock()
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /sessions — create_session
# ---------------------------------------------------------------------------

def test_create_session_returns_session_id(client):
    """POST /sessions with a valid topic request must return a session_id."""
    with (
        patch("app.routers.sessions.create_session_status"),
        patch("app.routers.sessions.asyncio.create_task"),
    ):
        response = client.post(
            "/sessions",
            json={
                "topic_description": "Introduction to machine learning algorithms",
                "tutoring_type": "advanced",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert isinstance(body["session_id"], str)
    assert len(body["session_id"]) > 0


def test_create_session_url_input(client):
    """POST /sessions with a URL must succeed and return a session_id."""
    with (
        patch("app.routers.sessions.create_session_status"),
        patch("app.routers.sessions.asyncio.create_task"),
    ):
        response = client.post(
            "/sessions",
            json={
                "url": "https://example.com/article",
                "tutoring_type": "teaching_a_kid",
            },
        )
    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_with_flashcards_and_quiz_flags(client):
    """POST /sessions must accept both opt-in flags without error."""
    with (
        patch("app.routers.sessions.create_session_status"),
        patch("app.routers.sessions.asyncio.create_task"),
    ):
        response = client.post(
            "/sessions",
            json={
                "paste_text": "Study text for a test session covering basic concepts.",
                "tutoring_type": "advanced",
                "generate_flashcards": True,
                "generate_quiz": True,
            },
        )
    assert response.status_code == 200
    assert "session_id" in response.json()


def test_create_session_topic_too_short_returns_422(client):
    """POST /sessions with a topic shorter than 10 chars must return 422."""
    response = client.post(
        "/sessions",
        json={
            "topic_description": "ML",
            "tutoring_type": "advanced",
        },
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /sessions/{id} — poll endpoint
# ---------------------------------------------------------------------------

def test_get_session_not_found(client):
    """GET /sessions/{id} for unknown session must return 404."""
    with patch("app.routers.sessions.get_session_status", return_value=None):
        response = client.get("/sessions/nonexistent-session-id")
    assert response.status_code == 404


def test_get_session_pending(client):
    """GET /sessions/{id} returns { status: pending } while workflow is running."""
    with patch(
        "app.routers.sessions.get_session_status",
        return_value={"status": "pending", "error_kind": "", "error_message": ""},
    ):
        response = client.get("/sessions/some-session-id")
    assert response.status_code == 200
    assert response.json() == {"status": "pending"}


def test_get_session_failed(client):
    """GET /sessions/{id} returns { status: failed, error_kind, error_message }."""
    with patch(
        "app.routers.sessions.get_session_status",
        return_value={
            "status": "failed",
            "error_kind": "rate_limit",
            "error_message": "Too many requests",
        },
    ):
        response = client.get("/sessions/some-session-id")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_kind"] == "rate_limit"
    assert "error_message" in body


def test_get_session_complete(client):
    """GET /sessions/{id} returns full session data when status is complete."""
    # agno stores session data nested under "session_state" key
    inner_state = {
        "title": "Test Session",
        "tutoring_type": "advanced",
        "session_type": "url",
        "sources": [],
        "notes": "## Notes\n- point one",
        "flashcards": [],
        "quiz": [],
        "chat_intro": "Hello!",
    }
    mock_session = MagicMock()
    mock_session.session_data = {"session_state": inner_state}
    mock_workflow = MagicMock()
    mock_workflow.get_session.return_value = mock_session

    with (
        patch(
            "app.routers.sessions.get_session_status",
            return_value={"status": "complete", "error_kind": "", "error_message": ""},
        ),
        patch("app.routers.sessions.build_session_workflow", return_value=mock_workflow),
    ):
        response = client.get("/sessions/some-session-id")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["source_title"] == "Test Session"
    assert body["notes"] == "## Notes\n- point one"
    assert body["session_id"] == "some-session-id"
    assert "was_truncated" in body
    assert body["was_truncated"] is False


# ---------------------------------------------------------------------------
# POST /sessions/{id}/regenerate/{section}
# ---------------------------------------------------------------------------

def test_regenerate_unknown_section_returns_400(client):
    """POST /sessions/{id}/regenerate/invalid_section must return 400."""
    response = client.post(
        "/sessions/any-session-id/regenerate/invalid_section",
        json={"tutoring_type": "advanced"},
    )
    assert response.status_code == 400


def test_regenerate_unknown_session_returns_404(client):
    """POST /sessions/{id}/regenerate/flashcards for unknown session must return 404."""
    with patch(
        "app.routers.sessions.get_session_status",
        return_value=None,
    ):
        response = client.post(
            "/sessions/nonexistent/regenerate/flashcards",
            json={"tutoring_type": "advanced"},
        )
    assert response.status_code == 404


def test_regenerate_pending_session_returns_409(client):
    """POST /sessions/{id}/regenerate/flashcards for a still-processing session must return 409."""
    with patch(
        "app.routers.sessions.get_session_status",
        return_value={"status": "pending", "error_kind": "", "error_message": ""},
    ):
        response = client.post(
            "/sessions/pending-session/regenerate/flashcards",
            json={"tutoring_type": "advanced"},
        )
    assert response.status_code == 409


def test_regenerate_flashcards_loads_source_content_from_sqlite(client):
    """POST /{id}/regenerate/flashcards with only tutoring_type reads source_content from SQLite."""
    inner_state = {"source_content": "Raw source text for flashcard generation.", "tutoring_type": "advanced"}
    mock_session = MagicMock()
    mock_session.session_data = {"session_state": inner_state}
    mock_workflow = MagicMock()
    mock_workflow.get_session.return_value = mock_session
    mock_workflow.asave_session = AsyncMock()

    async def fake_flashcards_step(step_input, session_state):
        session_state["flashcards"] = [{"front": "Q", "back": "A"}]

    with (
        patch(
            "app.routers.sessions.get_session_status",
            return_value={"status": "complete", "error_kind": "", "error_message": ""},
        ),
        patch("app.routers.sessions.build_session_workflow", return_value=mock_workflow),
        patch("app.routers.sessions.flashcards_step", side_effect=fake_flashcards_step),
    ):
        response = client.post(
            "/sessions/some-session-id/regenerate/flashcards",
            json={"tutoring_type": "advanced"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "flashcards" in body


def test_regenerate_returns_404_when_sqlite_has_no_source_content(client):
    """POST /{id}/regenerate/flashcards returns 404 when session state has no source_content key."""
    mock_session = MagicMock()
    mock_session.session_data = {"session_state": {}}  # no source_content key
    mock_workflow = MagicMock()
    mock_workflow.get_session.return_value = mock_session

    with (
        patch(
            "app.routers.sessions.get_session_status",
            return_value={"status": "complete", "error_kind": "", "error_message": ""},
        ),
        patch("app.routers.sessions.build_session_workflow", return_value=mock_workflow),
    ):
        response = client.post(
            "/sessions/no-notes-session/regenerate/flashcards",
            json={"tutoring_type": "advanced"},
        )
    assert response.status_code == 404


def test_chat_stream_request_model_has_no_notes_field():
    """ChatStreamRequest must not have a notes field — API-02 contract."""
    from app.models.chat import ChatStreamRequest
    fields = ChatStreamRequest.model_fields
    assert "notes" not in fields, f"ChatStreamRequest must not have notes field, found: {list(fields.keys())}"
