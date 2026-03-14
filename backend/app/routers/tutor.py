import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from agno.db.sqlite import SqliteDb
from agno.exceptions import InputCheckError

from app.models.tutor import TutorStreamRequest
from app.agents.tutor_team import build_tutor_team, TUTOR_TOKEN_EVENTS, TUTOR_ERROR_EVENT
from app.dependencies import get_traces_db, limiter
from app.config import get_settings
from app.workflows.session_workflow import build_session_workflow

logger = logging.getLogger("super_tutor.tutor")
router = APIRouter()


@router.post("/{session_id}/stream")
@limiter.limit(get_settings().rate_limit_tutor)
async def tutor_stream(session_id: str, request: Request, body: TutorStreamRequest, traces_db: SqliteDb = Depends(get_traces_db)):
    """
    Accept: JSON body with message, tutoring_type, session_id.
    source_content and notes are loaded from SQLite session state via session_id.
    Return: SSE stream of stream_start, token events, and a final done event.

    Conversation history is stored in SQLite under the `tutor:{session_id}` namespace
    and replayed on every request (TUTOR-03 persistence requirement).

    CRITICAL: Uses team.arun(stream=True) — a native async generator in agno 2.5.8.
    Do NOT use asyncio.to_thread here (RESEARCH.md Pitfall 1: breaks streaming).
    """
    # Load session from SQLite session state — authoritative source.
    try:
        wf = build_session_workflow(session_id=session_id, session_db=traces_db)
        session = wf.get_session(session_id=session_id)
    except Exception as e:
        logger.error("Failed to load session for tutor — session_id=%s error=%s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load session data. Please try again.")

    # session_data is the top-level dict; session_state is nested inside it
    session_state = (session.session_data or {}).get("session_state", {}) if session else {}
    if not session or not session_state:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Please create a new session.",
        )

    # Extract content fields from session state
    source_content = session_state.get("source_content", "")
    notes = session_state.get("notes", "")

    # Guard: source_content is required — the tutor cannot function without session material.
    # Returns HTTP 422 per CONTEXT.md locked decision (client error: session is incomplete).
    if not source_content.strip():
        raise HTTPException(
            status_code=422,
            detail="Session has no source content. The tutor requires source material to function.",
        )

    # Namespace the session_id to avoid collision with the workflow session row.
    # agno_sessions uses session_id as primary key — sharing the same id would cause
    # the team to overwrite the workflow's session_data (which holds source_content and notes).
    # See RESEARCH.md Pitfall 3.
    tutor_session_id = f"tutor:{session_id}"

    # Build team — per-request factory, never reuse across requests.
    team = build_tutor_team(
        source_content=source_content,
        notes=notes,
        tutoring_type=body.tutoring_type,
        db=traces_db,
        session_topic=source_content[:300],  # First 300 chars — sufficient for guardrail topic context
    )

    logger.info(
        "Tutor stream start",
        extra={"session_id": session_id, "tutoring_type": body.tutoring_type},
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        # Emit stream_start so the frontend can show a typing indicator
        # before the first token arrives (Claude's Discretion — RESEARCH.md Open Question 4).
        yield {"event": "stream_start", "data": json.dumps({})}
        try:
            run_errored = False
            async for chunk in team.arun(body.message, stream=True, session_id=tutor_session_id):
                if chunk.event == TUTOR_ERROR_EVENT:
                    run_errored = True
                    break
                # Capture both TeamRunContent (coordinator prefix) and
                # TeamRunIntermediateContent (Explainer tokens).
                # CRITICAL: Do NOT use RunEvent values here — Team uses TeamRunEvent.
                # See RESEARCH.md Pitfall 2 for why filtering only one event breaks streaming.
                if chunk.event in TUTOR_TOKEN_EVENTS and chunk.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk.content}),
                    }

            if run_errored:
                logger.warning("Tutor run error event received — session_id=%s", session_id)
                yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}
                return

            logger.info("Tutor stream done", extra={"session_id": session_id})
            yield {"event": "done", "data": json.dumps({})}

        except InputCheckError as e:
            # GUARD-01: topic guardrail rejected the message — friendly redirect, not a server error.
            logger.info("Topic guardrail triggered — session_id=%s message=%s", session_id, str(e)[:100])
            yield {
                "event": "rejected",
                "data": json.dumps({
                    "reason": "That's outside what we're studying today. Let's stay focused on the session material."
                }),
            }
        except Exception as e:
            logger.error("Tutor stream error: %s", e, exc_info=True, extra={"session_id": session_id})
            yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}

    return EventSourceResponse(event_generator())
