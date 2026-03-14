from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.agents.guardrails import PROMPT_INJECTION_GUARDRAIL, validate_substantive_output
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS
from app.config import get_settings


def build_chat_agent(tutoring_type: str, notes: str, db: SqliteDb | None = None) -> Agent:
    """
    Build a chat agent grounded in the provided session notes.
    A new agent is constructed on every request; conversation history is
    stored in the DB and replayed automatically via add_history_to_context.
    num_history_runs limits how many past turns are injected into context,
    bounding token cost on long conversations.
    """
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="ChatAgent",
        model=get_model(),
        db=db,
        add_history_to_context=True,
        num_history_runs=get_settings().chat_history_window,
        enable_session_summaries=False,
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        post_hooks=[validate_substantive_output],
        instructions=f"""{persona}

You are a tutoring assistant helping a student understand the session material below.
Answer ONLY from the session material. If the student's question is not covered in the
material, respond: "I can only answer about this session's material."
Do not use outside knowledge under any circumstances.

RESPONSE FORMAT: Plain text only. No markdown, no bullet points, no bold text, no tables,
no headers, no HTML tags. Write in clear, concise prose. Keep answers brief and direct —
two or three sentences is usually enough. Only elaborate if the student explicitly asks.

--- SESSION MATERIAL ---
{notes}
--- END MATERIAL ---""",
    )
