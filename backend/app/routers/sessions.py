import asyncio
import json
import logging
import os
import sqlite3
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.models.session import SessionRequest
from app.extraction.chain import extract_content, ExtractionError
from app.workflows.session_workflow import run_session_workflow, build_session_workflow, _get_session_db, _parse_json_safe
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.config import get_settings
from app.utils.retry import run_with_retry, is_retryable
from agno.db.sqlite import SqliteDb


def _get_traces_db() -> SqliteDb:
    """Lazy singleton for the shared trace db — avoids circular import from main.py.
    Uses the same db_file path and id='super_tutor_traces' as main.py and chat.py
    so rows from all three SqliteDb objects land in the same SQLite table.
    """
    if not hasattr(_get_traces_db, "_instance"):
        settings = get_settings()
        _get_traces_db._instance = SqliteDb(
            db_file=settings.trace_db_path,
            id="super_tutor_traces",
        )
    return _get_traces_db._instance

def _guard_session(session_id: str) -> None:
    """Raise HTTP 404 if session_id has no stored workflow session in SQLite."""
    wf = build_session_workflow(session_id=session_id, session_db=_get_session_db())
    existing = wf.get_session(session_id=session_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found or expired. Please create a new session.",
        )


logger = logging.getLogger("super_tutor.sessions")

router = APIRouter()

# In-memory store for pending (not-yet-streamed) session params only.
# Completed session data is sent in full via the SSE complete event and stored client-side.
PENDING_STORE: dict[str, dict] = {}   # session_id -> raw request params


def _params_db_path() -> str:
    """SQLite file path for persisting pending session params across restarts."""
    db_dir = os.path.dirname(get_settings().session_db_path)
    return os.path.join(db_dir or "tmp", "session_pending_params.db")


def _save_pending_params(session_id: str, params: dict) -> None:
    """Persist session params to SQLite so they survive a backend restart."""
    path = _params_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_params"
            " (session_id TEXT PRIMARY KEY, params TEXT)"
        )
        conn.execute(
            "INSERT OR REPLACE INTO pending_params VALUES (?, ?)",
            (session_id, json.dumps(params)),
        )


def _pop_pending_params(session_id: str) -> dict | None:
    """Read and delete persisted params; returns None if not found."""
    path = _params_db_path()
    if not os.path.exists(path):
        return None
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS pending_params"
            " (session_id TEXT PRIMARY KEY, params TEXT)"
        )
        row = conn.execute(
            "SELECT params FROM pending_params WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM pending_params WHERE session_id = ?", (session_id,))
            return json.loads(row[0])
    return None


class RegenerateRequest(BaseModel):
    notes: str
    tutoring_type: str


@router.post("")
async def create_session(request: SessionRequest):
    """
    Step 1 of the two-step SSE flow.
    Stores session params and returns a session_id for the stream endpoint.
    """
    session_id = str(uuid.uuid4())
    params = request.model_dump(mode="json")
    PENDING_STORE[session_id] = params
    _save_pending_params(session_id, params)
    logger.info(
        "Session created — session_id=%s input_type=%s tutoring_type=%s",
        session_id,
        "topic" if request.topic_description else ("paste" if request.paste_text else "url"),
        request.tutoring_type,
    )
    return {"session_id": session_id}


@router.get("/{session_id}/stream")
async def stream_session(session_id: str):
    """
    Step 2: Opens the SSE stream. Runs the extraction + workflow pipeline.
    Emits 'progress' events with messages, then a 'complete' or 'error' event.
    """
    params = PENDING_STORE.pop(session_id, None)
    if params is None:
        # PENDING_STORE was cleared (backend restart) — fall back to SQLite persistence
        params = _pop_pending_params(session_id)
        if params is None:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        _pop_pending_params(session_id)  # clean up SQLite mirror
    logger.info("Stream opened — session_id=%s", session_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        url = params.get("url") or ""
        paste_text = params.get("paste_text") or ""
        topic_description = params.get("topic_description") or ""
        tutoring_type = params["tutoring_type"]
        focus_prompt = params.get("focus_prompt") or ""

        session_type = "url"
        content = ""

        # Input validation: topic too short
        if topic_description and len(topic_description.strip()) < 10:
            yield {
                "event": "error",
                "data": json.dumps({"kind": "invalid_url", "message": "Topic description is too short. Please describe what you want to learn."}),
            }
            return

        try:
            if topic_description:
                session_type = "topic"
                # source_content is empty for topic sessions; workflow's research_step fetches it
                content = ""
            elif paste_text:
                content = paste_text
            elif url:
                yield {
                    "event": "progress",
                    "data": json.dumps({"message": "Reading the article..."}),
                }
                try:
                    content = await extract_content(str(url))
                except ExtractionError as e:
                    logger.warning("Extraction error — session_id=%s kind=%s message=%s", session_id, e.kind, e.message)
                    yield {
                        "event": "error",
                        "data": json.dumps({"kind": e.kind, "message": e.message}),
                    }
                    return
            else:
                yield {
                    "event": "error",
                    "data": json.dumps({"kind": "invalid_url", "message": "No URL, text, or topic provided"}),
                }
                return

        except ExtractionError as e:
            logger.warning("Extraction error — session_id=%s kind=%s message=%s", session_id, e.kind, e.message)
            yield {
                "event": "error",
                "data": json.dumps({"kind": e.kind, "message": e.message}),
            }
            return

        # Step 2: Run the AI workflow, streaming progress events
        try:
            async for response in run_session_workflow(
                session_id=session_id,
                session_type=session_type,
                source_content=content,
                topic_description=topic_description,
                tutoring_type=tutoring_type,
                focus_prompt=focus_prompt,
                generate_flashcards=params.get("generate_flashcards", False),
                generate_quiz=params.get("generate_quiz", False),
                traces_db=_get_traces_db(),
            ):
                # Classify the response by event name
                event_name = getattr(response.event, "value", str(response.event)) if response.event else ""
                is_complete = "completed" in event_name or isinstance(response.content, dict)
                is_warning = "warning" in event_name

                if is_complete and isinstance(response.content, dict):
                    session_data = {"session_id": session_id, **response.content}
                    logger.info("Stream complete — session_id=%s", session_id)
                    yield {
                        "event": "complete",
                        "data": json.dumps(session_data),
                    }
                elif is_warning and isinstance(response.content, str):
                    yield {
                        "event": "warning",
                        "data": json.dumps({"message": response.content}),
                    }
                elif isinstance(response.content, str):
                    # Progress message
                    yield {
                        "event": "progress",
                        "data": json.dumps({"message": response.content}),
                    }

                # Yield control to the event loop so SSE frames flush between steps
                await asyncio.sleep(0)

        except Exception as e:
            logger.error("Workflow error — session_id=%s error=%s", session_id, e, exc_info=True)
            if is_retryable(e):
                user_msg = "The AI is temporarily busy — please try again in a moment."
            else:
                user_msg = "Something went wrong generating your session. Please try again."
            yield {
                "event": "error",
                "data": json.dumps({"kind": "empty", "message": user_msg}),
            }

    return EventSourceResponse(event_generator())


@router.get("/{session_id}")
async def get_session(session_id: str):
    """
    Fetch session data from SQLite.
    - 404: session never started (not in SQLite)
    - 202: session in progress (in SQLite but workflow not complete)
    - 200: session complete with full data
    """
    wf = build_session_workflow(session_id=session_id, session_db=_get_session_db())
    existing = wf.get_session(session_id=session_id)
    if existing is None:
        logger.warning("get_session — not found", extra={"session_id": session_id})
        raise HTTPException(status_code=404, detail="Session not found")
    state = existing.session_data or {}
    if not state.get("notes"):
        logger.info("get_session — pending", extra={"session_id": session_id})
        return JSONResponse(status_code=202, content={"status": "pending"})
    logger.info("get_session — found", extra={"session_id": session_id})
    return {
        "session_id": session_id,
        "source_title": state.get("title", "Study Session"),
        "tutoring_type": state.get("tutoring_type", ""),
        "session_type": state.get("session_type", "url"),
        "sources": state.get("sources", []),
        "notes": state.get("notes"),
        "flashcards": state.get("flashcards", []),
        "quiz": state.get("quiz", []),
        "chat_intro": state.get("chat_intro", ""),
    }


@router.post("/{session_id}/regenerate/{section}")
async def regenerate_section(session_id: str, section: str, body: RegenerateRequest):
    """Generates flashcards or quiz on demand using notes + tutoring_type from the client."""
    if section not in ("flashcards", "quiz"):
        raise HTTPException(status_code=400, detail="section must be 'flashcards' or 'quiz'")

    # STOR-03: reject unknown/expired session_id with a clear 404
    _guard_session(session_id)

    input_text = f"Content:\n{body.notes}"

    logger.info("Generating %s — session_id=%s tutoring_type=%s", section, session_id, body.tutoring_type)

    settings = get_settings()
    if section == "flashcards":
        agent = build_flashcard_agent(body.tutoring_type, db=_get_traces_db())
        result = await asyncio.to_thread(
            run_with_retry, agent.run, input_text,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,  # TRAC-04
        )
        new_items = _parse_json_safe(result.content or "[]", [])
        if not new_items:
            raise HTTPException(status_code=500, detail="Generation returned empty response")
        logger.info("Generation complete — session_id=%s section=flashcards count=%d", session_id, len(new_items))
        return {"flashcards": new_items}
    else:
        agent = build_quiz_agent(body.tutoring_type, db=_get_traces_db())
        result = await asyncio.to_thread(
            run_with_retry, agent.run, input_text,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,  # TRAC-04
        )
        new_items = _parse_json_safe(result.content or "[]", [])
        if not new_items:
            raise HTTPException(status_code=500, detail="Generation returned empty response")
        logger.info("Generation complete — session_id=%s section=quiz count=%d", session_id, len(new_items))
        return {"quiz": new_items}
