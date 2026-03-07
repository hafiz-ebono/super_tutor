from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.models.message import Message
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS


def build_chat_agent(tutoring_type: str, notes: str, db: SqliteDb | None = None) -> Agent:
    """
    Build a stateless chat agent grounded in the provided session notes.
    A new agent is constructed on every request — no server-side state.
    The persona from PERSONAS adapts tone to the tutoring mode (CHAT-06).
    The grounding instruction enforces notes-only responses (CHAT-05).
    """
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="ChatAgent",
        model=get_model(),
        db=db,
        enable_session_summaries=True,
        instructions=f"""{persona}

You are a tutoring assistant helping a student understand the session material below.
Answer ONLY from the session material. If the student's question is not covered in the
material, respond: "I can only answer about this session's material."
Do not use outside knowledge under any circumstances.

# TODO: truncate notes if > 3000 tokens (current notes are compressed, safe for MVP)

--- SESSION MATERIAL ---
{notes}
--- END MATERIAL ---""",
    )


def build_chat_messages(
    history: list[dict],  # [{"role": "user"|"assistant", "content": str}]
    message: str,
) -> list[Message]:
    """
    Converts frontend history list + current message into List[Message] for agent.arun().

    Agno 2.5.2 handles List[Message] in step 5 of get_run_messages():
    when input is a List[Message], Agno appends them after the system prompt
    and does NOT create an additional user message. The final Message(role="user")
    in this list IS the current user turn.

    History is capped at 6 turns on the client side (STATE.md decision).
    The backend accepts whatever the client sends — no server-side cap.
    """
    messages = [Message(role=turn["role"], content=turn["content"]) for turn in history]
    messages.append(Message(role="user", content=message))
    return messages
