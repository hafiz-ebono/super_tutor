import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatStreamRequest
from app.agents.chat_agent import build_chat_agent, build_chat_messages

logger = logging.getLogger("super_tutor.chat")
router = APIRouter()


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    Accept: JSON body with message, notes, tutoring_type, history (list of {role, content}).
    Return: SSE stream of {"event": "token", "data": {"token": "..."}} chunks,
            terminated by {"event": "done"}.

    History is stateless — the client sends the last N turns on every request (capped at 6,
    STATE.md decision). The backend does not store or enforce the cap.

    CRITICAL: Uses agent.arun(stream=True) — a native async generator.
    Do NOT use asyncio.to_thread here (RESEARCH.md Pitfall 1: breaks streaming).
    """
    agent = build_chat_agent(request.tutoring_type, request.notes)
    messages = build_chat_messages(
        [m.model_dump() for m in request.history],
        request.message,
    )

    logger.info(
        "Chat stream — tutoring_type=%s history_turns=%d",
        request.tutoring_type,
        len(request.history),
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for chunk in agent.arun(messages, stream=True):
                # RunEvent.run_content == "RunContent" (str enum from agno/run/agent.py)
                # Only yield content events — filter out RunStarted, ToolCallStarted, etc.
                if chunk.event == "RunContent" and chunk.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk.content}),
                    }
            yield {"event": "done", "data": json.dumps({})}
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True)
            from app.utils.retry import is_retryable
            if is_retryable(e):
                user_message = "The AI is temporarily busy — please try again in a moment."
            else:
                user_message = "Something went wrong. Please try again."
            yield {"event": "error", "data": json.dumps({"error": user_message})}

    return EventSourceResponse(event_generator())
