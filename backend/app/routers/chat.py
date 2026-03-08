import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatStreamRequest
from app.agents.chat_agent import build_chat_agent, build_chat_messages
from app.config import get_settings
from app.workflows.session_workflow import build_session_workflow, _get_session_db
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
    # Load notes from SQLite session state — authoritative source, not client-supplied
    wf = build_session_workflow(session_id=request.session_id, session_db=_get_session_db())
    session = wf.get_session(session_id=request.session_id)
    if session is None or not session.session_state:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please create a new session.",
        )
    notes = session.session_state.get("notes", "")
    if not notes:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' has no notes. Please create a new session.",
        )

    agent = build_chat_agent(request.tutoring_type, notes, db=_get_traces_db())
    messages = build_chat_messages(
        [m.model_dump() for m in request.history],
        request.message,
    )

    logger.info(
        "Chat stream start",
        extra={"session_id": request.session_id, "tutoring_type": request.tutoring_type, "history_turns": len(request.history)},
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for chunk in agent.arun(messages, stream=True, session_id=request.session_id):
                # RunEvent.run_content == "RunContent" (str enum from agno/run/agent.py)
                # Only yield content events — filter out RunStarted, ToolCallStarted, etc.
                if chunk.event == "RunContent" and chunk.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk.content}),
                    }
            if request.session_id:
                try:
                    await agent.aset_session_name(
                        session_id=request.session_id,
                        session_name=request.message,
                    )
                except Exception as e:
                    logger.warning("Could not set session name: %s", e)
            logger.info("Chat stream done", extra={"session_id": request.session_id})
            yield {"event": "done", "data": json.dumps({})}
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True, extra={"session_id": request.session_id})
            from app.utils.retry import is_retryable
            if is_retryable(e):
                user_message = "The AI is temporarily busy — please try again in a moment."
            else:
                user_message = "Something went wrong. Please try again."
            yield {"event": "error", "data": json.dumps({"error": user_message})}

    return EventSourceResponse(event_generator())
