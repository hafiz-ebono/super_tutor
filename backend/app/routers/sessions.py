import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.session import SessionRequest
from app.extraction.chain import extract_content, ExtractionError
from app.workflows.session_workflow import build_workflow
from app.agents.research_agent import run_research

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

    async def event_generator() -> AsyncGenerator[dict, None]:
        url = params.get("url") or ""
        paste_text = params.get("paste_text") or ""
        topic_description = params.get("topic_description") or ""
        tutoring_type = params["tutoring_type"]
        focus_prompt = params.get("focus_prompt") or ""

        session_type = "url"
        sources = None
        title_hint = ""

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

                result = run_research(topic_description, focus_prompt)
                content = result.content
                sources = result.sources if result.sources else []
                title_hint = " ".join(topic_description.split()[:5])

                if not content or len(content.strip()) < 100:
                    # Research failed or returned too little content — fall back to LLM knowledge
                    content = f"Topic: {topic_description}\n\nFocus: {focus_prompt}" if focus_prompt else f"Topic: {topic_description}"
                    sources = []
                    title_hint = " ".join(topic_description.split()[:5])
                    yield {
                        "event": "warning",
                        "data": json.dumps({"message": "Live research was unavailable — content was generated from AI knowledge. Verify with primary sources."}),
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
                title_hint=title_hint,
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
