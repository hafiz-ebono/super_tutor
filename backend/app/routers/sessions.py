import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.session import SessionRequest
from app.extraction.chain import extract_content, ExtractionError
from app.workflows.session_workflow import build_workflow
from app.agents.research_agent import run_research

logger = logging.getLogger("super_tutor.sessions")

router = APIRouter()

# In-memory session storage: session_id -> dict with pending params or completed SessionResult
# Phase 1 only — no database, ephemeral per server restart
PENDING_STORE: dict[str, dict] = {}   # session_id -> raw request params
SESSION_STORE: dict[str, dict] = {}   # session_id -> completed session data


@router.post("")
async def create_session(request: SessionRequest):
    """
    Step 1 of the two-step SSE flow.
    Stores session params and returns a session_id for the stream endpoint.
    """
    session_id = str(uuid.uuid4())
    PENDING_STORE[session_id] = request.model_dump(mode="json")
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
    if session_id not in PENDING_STORE:
        raise HTTPException(status_code=404, detail="Session not found")

    params = PENDING_STORE.pop(session_id)
    logger.info("Stream opened — session_id=%s", session_id)

    async def event_generator() -> AsyncGenerator[dict, None]:
        url = params.get("url") or ""
        paste_text = params.get("paste_text") or ""
        topic_description = params.get("topic_description") or ""
        tutoring_type = params["tutoring_type"]
        focus_prompt = params.get("focus_prompt") or ""

        session_type = "url"
        sources = None
        # title_input: the focused signal passed to AI title generation.
        # Topic sessions use topic_description (short, precise).
        # URL/paste sessions pass empty string so the workflow uses the extracted content.
        title_input = ""

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
                title_input = topic_description

                # Vague topic detection: fewer than 3 words
                word_count = len(topic_description.split())
                if word_count < 3:
                    yield {
                        "event": "warning",
                        "data": json.dumps({"message": "Your topic is quite broad — we'll do our best, but the content may be general. Consider adding more detail for better results."}),
                    }
                    await asyncio.sleep(0)

                yield {
                    "event": "progress",
                    "data": json.dumps({"message": "Researching your topic..."}),
                }
                await asyncio.sleep(0)

                try:
                    result = run_research(topic_description, focus_prompt)
                except Exception as e:
                    logger.error("Research failed — session_id=%s error=%s", session_id, e, exc_info=True)
                    yield {
                        "event": "error",
                        "data": json.dumps({"kind": "empty", "message": f"Research failed: {e}. Please try again."}),
                    }
                    return

                content = result.content
                sources = result.sources if result.sources else []

                if not content or len(content.strip()) < 100:
                    # Model returned too little — not a hard failure, continue with LLM knowledge
                    content = f"Topic: {topic_description}\n\nFocus: {focus_prompt}" if focus_prompt else f"Topic: {topic_description}"
                    sources = []
                    yield {
                        "event": "warning",
                        "data": json.dumps({"message": "Research returned limited content — notes were generated from AI knowledge instead."}),
                    }
                    await asyncio.sleep(0)

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
        workflow = build_workflow(tutoring_type)

        try:
            for response in workflow.run(
                content=content,
                tutoring_type=tutoring_type,
                focus_prompt=focus_prompt,
                url=str(params.get("url") or ""),
                session_type=session_type,
                sources=sources,
                title_input=title_input,
            ):
                # Check if this is the final completed response
                event_name = getattr(response.event, "value", str(response.event)) if response.event else ""
                is_complete = "completed" in event_name or isinstance(response.content, dict)

                if is_complete and isinstance(response.content, dict):
                    # Store the full session result
                    session_data = {
                        "session_id": session_id,
                        **response.content,
                    }
                    SESSION_STORE[session_id] = session_data
                    logger.info("Stream complete — session_id=%s", session_id)
                    yield {
                        "event": "complete",
                        "data": json.dumps({"session_id": session_id}),
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
            yield {
                "event": "error",
                "data": json.dumps({"kind": "empty", "message": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Returns the completed session data. Called after stream completes."""
    if session_id not in SESSION_STORE:
        raise HTTPException(status_code=404, detail="Session not found or not yet complete")
    return SESSION_STORE[session_id]
