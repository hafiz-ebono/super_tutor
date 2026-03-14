"""
Router tests for POST /sessions/upload SSE endpoint.

Tests exercise the HTTP layer without hitting real AI agents, databases,
or file extraction. All external side-effects are patched out.

Pattern mirrors test_sessions_router.py: sync TestClient, per-test patches,
no asyncio marks.
"""
import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import upload as upload_router
from app.extraction.document_extractor import DocumentExtractionError


# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(upload_router.router, prefix="/sessions")
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_sse_events(lines):
    """Parse SSE data lines from an iterable of text lines."""
    events = []
    current_event_type = "message"
    for line in lines:
        if line.startswith("event:"):
            current_event_type = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                events.append({"event": current_event_type, "data": json.loads(data_str)})
            except json.JSONDecodeError:
                events.append({"event": current_event_type, "data": data_str})
            current_event_type = "message"  # reset after data line
    return events


# ---------------------------------------------------------------------------
# TEST 1 — Happy path: valid PDF produces SSE stream with required events
# ---------------------------------------------------------------------------


@patch("app.routers.upload.extract_document", return_value="Extracted study content " * 20)
@patch("app.routers.upload.run_workflow_background", new_callable=AsyncMock)
@patch("app.routers.upload.create_session_status")
def test_valid_pdf_produces_sse_stream(mock_create_status, mock_workflow, mock_extract, client):
    """POST /sessions/upload with a valid PDF returns a 200 SSE stream with progress and complete events."""
    pdf_bytes = b"%PDF fake"
    with client.stream(
        "POST",
        "/sessions/upload",
        files={"file": ("notes.pdf", pdf_bytes, "application/pdf")},
        data={"tutoring_type": "advanced"},
    ) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    events = parse_sse_events(lines)
    event_types = [e["event"] for e in events]
    messages = [
        e["data"].get("message", "")
        for e in events
        if isinstance(e["data"], dict)
    ]

    # Must include a progress event with "Reading your file..." message
    assert any("Reading your file" in m for m in messages), (
        f"Expected 'Reading your file...' in SSE messages; got: {messages}"
    )

    # Must include exactly one 'complete' event with session_id
    complete_events = [e for e in events if e["event"] == "complete"]
    assert len(complete_events) == 1, (
        f"Expected exactly 1 'complete' event; got: {complete_events}"
    )
    assert "session_id" in complete_events[0]["data"], (
        f"'complete' event must carry session_id; got: {complete_events[0]}"
    )


# ---------------------------------------------------------------------------
# TEST 2 — Valid .docx file produces SSE stream with required events
# ---------------------------------------------------------------------------


@patch("app.routers.upload.extract_document", return_value="Extracted study content " * 20)
@patch("app.routers.upload.run_workflow_background", new_callable=AsyncMock)
@patch("app.routers.upload.create_session_status")
def test_valid_docx_produces_sse_stream(mock_create_status, mock_workflow, mock_extract, client):
    """POST /sessions/upload with a valid .docx returns a 200 SSE stream with progress and complete events."""
    docx_bytes = b"PK\x03\x04"
    with client.stream(
        "POST",
        "/sessions/upload",
        files={"file": ("lecture.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"tutoring_type": "advanced"},
    ) as response:
        assert response.status_code == 200
        lines = list(response.iter_lines())

    events = parse_sse_events(lines)
    messages = [
        e["data"].get("message", "")
        for e in events
        if isinstance(e["data"], dict)
    ]

    # Must include a progress event with "Reading your file..." message
    assert any("Reading your file" in m for m in messages), (
        f"Expected 'Reading your file...' in SSE messages; got: {messages}"
    )

    # Must include exactly one 'complete' event with session_id
    complete_events = [e for e in events if e["event"] == "complete"]
    assert len(complete_events) == 1, (
        f"Expected exactly 1 'complete' event; got: {complete_events}"
    )
    assert "session_id" in complete_events[0]["data"], (
        f"'complete' event must carry session_id; got: {complete_events[0]}"
    )


# ---------------------------------------------------------------------------
# TEST 3 — Unsupported file format returns HTTP 400 before SSE opens
# ---------------------------------------------------------------------------


def test_unsupported_format_returns_400(client):
    """POST /sessions/upload with a .txt file returns HTTP 400 with error_kind='unsupported_format'."""
    response = client.post(
        "/sessions/upload",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
        data={"tutoring_type": "advanced"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error_kind"] == "unsupported_format"


# ---------------------------------------------------------------------------
# TEST 4 — Scanned PDF returns HTTP 422 with error_kind="scanned_pdf"
# ---------------------------------------------------------------------------


@patch(
    "app.routers.upload.extract_document",
    side_effect=DocumentExtractionError(
        error_kind="scanned_pdf",
        message="This PDF appears to be scanned or image-based.",
    ),
)
def test_scanned_pdf_returns_422(mock_extract, client):
    """POST /sessions/upload with a scanned PDF returns HTTP 422 with error_kind='scanned_pdf'."""
    pdf_bytes = b"%PDF scanned"
    response = client.post(
        "/sessions/upload",
        files={"file": ("scan.pdf", pdf_bytes, "application/pdf")},
        data={"tutoring_type": "advanced"},
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["error_kind"] == "scanned_pdf"


# ---------------------------------------------------------------------------
# TEST 5 — Oversized file returns HTTP 413
# ---------------------------------------------------------------------------


def test_oversized_file_returns_413(client):
    """POST /sessions/upload with a >20 MB file returns HTTP 413 with error_kind='file_too_large'."""
    # 21 MB — just above the 20 MB limit
    large_bytes = b"%PDF " + b"A" * (21 * 1024 * 1024)
    response = client.post(
        "/sessions/upload",
        files={"file": ("big.pdf", large_bytes, "application/pdf")},
        data={"tutoring_type": "advanced"},
    )
    assert response.status_code == 413
    detail = response.json()["detail"]
    assert detail["error_kind"] == "file_too_large"


# ---------------------------------------------------------------------------
# SC4 — Verify POST /sessions (existing endpoint) is unaffected
# ---------------------------------------------------------------------------


def test_existing_sessions_route_unaffected_by_upload_router():
    """The upload router must NOT shadow or break the POST /sessions endpoint.

    SC4: mounting upload_router at /sessions adds /sessions/upload but does not
    affect /sessions itself, which is served by sessions_router.
    """
    from app.routers import sessions as sessions_router

    app = FastAPI()
    app.include_router(sessions_router.router, prefix="/sessions")
    app.include_router(upload_router.router, prefix="/sessions")
    c = TestClient(app)

    with (
        patch("app.routers.sessions.create_session_status"),
        patch("app.routers.sessions.asyncio.create_task"),
    ):
        response = c.post(
            "/sessions",
            json={
                "topic_description": "Introduction to machine learning algorithms",
                "tutoring_type": "advanced",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
