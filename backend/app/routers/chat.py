import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatStreamRequest
from app.agents.chat_agent import build_chat_agent
from app.config import get_settings
from app.workflows.session_workflow import build_session_workflow
from agno.db.sqlite import SqliteDb

logger = logging.getLogger("super_tutor.chat")
router = APIRouter()


def _get_traces_db() -> SqliteDb:
    """Return the shared trace db instance, creating it if needed (lazy singleton).
    Uses the same db_file path and id='super_tutor_traces' as main.py and sessions.py
    so all three SqliteDb objects write to the same SQLite file and table.
    """
    if not hasattr(_get_traces_db, "_instance"):
        settings = get_settings()
        _get_traces_db._instance = SqliteDb(
            db_file=settings.trace_db_path,
            id="super_tutor_traces",
        )
    return _get_traces_db._instance


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    Accept: JSON body with message, tutoring_type, history (list of {role, content}), session_id.
    Notes are loaded from SQLite session state via session_id (not accepted in the request body).
    Return: SSE stream of {"event": "token", "data": {"token": "..."}} chunks,
            terminated by {"event": "done"}.

    History is stateless — the client sends the last N turns on every request (capped at 6,
    STATE.md decision). The backend does not store or enforce the cap.

    CRITICAL: Uses agent.arun(stream=True) — a native async generator.
    Do NOT use asyncio.to_thread here (RESEARCH.md Pitfall 1: breaks streaming).
    """
    # Load notes from SQLite session state — authoritative source, not client-supplied.
    try:
        wf = build_session_workflow(session_id=request.session_id, session_db=_get_traces_db())
        session = wf.get_session(session_id=request.session_id)
    except Exception as e:
        logger.error("Failed to load session for chat — session_id=%s error=%s", request.session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load session data. Please try again.")

    # session_data is the top-level dict; session_state is nested inside it
    session_state = (session.session_data or {}).get("session_state", {}) if session else {}
    if not session or not session_state:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please create a new session.",
        )
    notes = session_state.get("notes", "")
    if not notes:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' has no notes. Please create a new session.",
        )

    # Namespace the chat session_id to avoid colliding with the workflow session row.
    # agno_sessions uses session_id as primary key — sharing the same id would cause
    # the chat agent to overwrite the workflow's session_data (which holds the notes).
    # If the client sends a chat_reset_id, append it so the agent starts a fresh DB session.
    chat_session_id = (
        f"chat:{request.session_id}:{request.chat_reset_id}"
        if request.chat_reset_id
        else f"chat:{request.session_id}"
    )

    agent = build_chat_agent(request.tutoring_type, notes, db=_get_traces_db())

    logger.info(
        "Chat stream start",
        extra={"session_id": request.session_id, "tutoring_type": request.tutoring_type},
    )

    session_title = session_state.get("title") or request.message

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            run_errored = False
            async for chunk in agent.arun(request.message, stream=True, session_id=chat_session_id):
                if chunk.event == "RunError":
                    run_errored = True
                    break
                # RunEvent.run_content == "RunContent" (str enum from agno/run/agent.py)
                # Only yield content events — filter out RunStarted, ToolCallStarted, etc.
                if chunk.event == "RunContent" and chunk.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk.content}),
                    }

            if run_errored:
                logger.warning("Chat run error event received", extra={"session_id": request.session_id})
                yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}
                return

            try:
                await agent.aset_session_name(
                    session_id=chat_session_id,
                    session_name=session_title,
                )
            except Exception as e:
                logger.warning("Could not set session name: %s", e)
            logger.info("Chat stream done", extra={"session_id": request.session_id})
            yield {"event": "done", "data": json.dumps({})}
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True, extra={"session_id": request.session_id})
            yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}

    return EventSourceResponse(event_generator())
