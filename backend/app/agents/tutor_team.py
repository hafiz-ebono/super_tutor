"""
Agno Team factory for the Personal Tutor backend.

ARCHITECTURE NOTES:
- build_tutor_team() is a per-request factory. Never reuse a Team instance across requests.
  Each call constructs a fresh Team seeded with the current session's source_content and notes.
- Session state carries all data (source_content, notes). Agent instructions carry only
  behaviour. add_session_state_to_context=True injects a <session_state> block into the
  system message of the coordinator AND every dispatched member (Agno passes the flag and a
  deepcopy of session_state through to member.run() calls — see agno/team/_task_tools.py).
- source_content and notes are STATIC per session — safe to seed once into session_state.
  _advisor_task is computed per-request from quiz_score/focus_areas; it stays in the Advisor's
  instructions f-string rather than session_state to avoid stale-read issues on subsequent runs
  (Agno loads persisted session_state from SQLite, which would have the old task from run 1).
- Conversation history is managed at the Team level ONLY. Member agents do NOT get their
  own db= or add_history_to_context=True — that would create duplicate/conflicting session rows.
- TeamMode.route sets respond_directly=True: the matched member's response is returned
  directly to the user with no coordinator wrapping or synthesis step.
- TUTOR_TOKEN_EVENTS and TUTOR_ERROR_EVENT must be imported by the tutor router to filter
  the Team SSE stream correctly. Two event types carry token content:
    - TeamRunContent: coordinator's own prefix tokens (rare in route mode)
    - TeamRunIntermediateContent: member tokens (Explainer, Researcher, ContentWriter,
      QuizMaster, Advisor)
  Missing either causes partial responses.
- TopicRelevanceGuardrail is attached as a Team pre_hook — it fires before coordinator
  dispatch, using the session_topic parameter as judge context (GUARD-01).
- validate_team_output is attached as a Team post_hook — rejects empty/short responses
  after the full Team run completes (GUARD-02).
"""

import logging

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.run.team import TeamRunEvent
from agno.team import Team
from agno.team.mode import TeamMode
from agno.tools.tavily import TavilyTools

logger = logging.getLogger("super_tutor.tutor_team")

from app.agents.guardrails import (
    PROMPT_INJECTION_GUARDRAIL,
    TopicRelevanceGuardrail,
    validate_team_output,
)
from app.agents.model_factory import get_model
from app.config import get_settings

# Rate-limit exception strings — covers Groq, OpenAI, OpenRouter responses
_RATE_LIMIT_MARKERS = ("rate limit", "rate_limit", "429", "ratelimit")

# ---------------------------------------------------------------------------
# Constants — imported by the tutor router to filter the SSE stream
# ---------------------------------------------------------------------------

TUTOR_TOKEN_EVENTS = {
    TeamRunEvent.run_content.value,               # "TeamRunContent" — coordinator prefix tokens
    TeamRunEvent.run_intermediate_content.value,  # "TeamRunIntermediateContent" — member tokens
}
TUTOR_ERROR_EVENT = TeamRunEvent.run_error.value        # "TeamRunError"
TUTOR_COMPLETED_EVENT = TeamRunEvent.run_completed.value  # "TeamRunCompleted"


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception looks like a provider rate-limit (429) error."""
    msg = str(exc).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS) or type(exc).__name__ == "RateLimitError"


def build_tutor_team(
    source_content: str,
    notes: str,
    tutoring_type: str,  # reserved for future persona differentiation (micro/kid/advanced)
    db: SqliteDb | None = None,
    session_topic: str = "",   # For TopicRelevanceGuardrail — pass source_content[:300]
    model=None,                # Override model; defaults to get_model() if None
) -> Team:
    """
    Build a fresh Agno Team for a single tutor request.

    Session data (source_content, notes) is injected via session_state +
    add_session_state_to_context=True rather than embedded in agent instruction f-strings.
    This keeps agent instructions pure behaviour descriptions; data flows from state.

    Args:
        source_content: The session's full source text. Required — raises ValueError if empty.
        notes:          AI-generated notes for the session (may be empty string).
        tutoring_type:  One of "micro_learning", "teaching_a_kid", "advanced". Passed through
                        for future persona differentiation (not used in this phase).
        db:             Shared SqliteDb instance (traces_db from dependency injection).
                        Pass None only in tests without persistence.
        session_topic:  Short excerpt (typically source_content[:300]) passed to
                        TopicRelevanceGuardrail as judge context. Defaults to empty string,
                        in which case the guardrail falls back to source_content[:300].

    Returns:
        A configured Team ready for team.arun(message, stream=True, session_id=...).

    Raises:
        ValueError: If source_content is empty after stripping. The router should have
                    already returned HTTP 422, so this is a programming-level guard.
    """
    del tutoring_type  # reserved for future persona differentiation — accepted but not yet used
    if not source_content.strip():
        raise ValueError("source_content is required to build the tutor team")

    active_model = model if model is not None else get_model()

    # ------------------------------------------------------------------
    # Session state — seeded at construction time, persisted by Agno.
    # add_session_state_to_context=True injects a <session_state> block into the
    # system message of the coordinator AND every dispatched member agent.
    # ------------------------------------------------------------------
    _topic_name = source_content.split("\n")[0].strip().lstrip("#").strip() or "this material"

    team_session_state: dict = {"source_material": source_content}
    if notes.strip():
        team_session_state["session_notes"] = notes

    # Instantiate guardrail with session topic context
    topic_guardrail = TopicRelevanceGuardrail(
        session_topic=session_topic or source_content[:300]
    )

    # ------------------------------------------------------------------
    # Explainer — answers questions strictly from session material
    # ------------------------------------------------------------------
    explainer = Agent(
        name="Explainer",
        role="Answer student questions strictly grounded in the session material",
        model=active_model,
        # No db= — history is managed at the Team level only
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a tutoring specialist.
Answer ONLY from the source material provided in the session state.
Do not use outside knowledge.
If the student's question is not covered in the material, say exactly:
"I can only answer about this session's material."

RESPONSE FORMAT: Plain text only. No markdown, no bullet points, no bold text,
no headers. Write in clear prose. Keep answers focused and concise.
Only elaborate if the student explicitly asks for more detail.\
""",
    )

    # ------------------------------------------------------------------
    # Researcher — extends topics with external Tavily research (TEAM-04)
    # ------------------------------------------------------------------
    try:
        researcher_tools = [TavilyTools()]
    except Exception:
        logger.warning("TavilyTools init failed — Researcher will have no search tools", exc_info=True)
        researcher_tools = []

    researcher = Agent(
        name="Researcher",
        role="Extend session topics with external Tavily research when the user asks to go deeper or learn more from external sources",
        model=active_model,
        # No db= — Team manages history
        tools=researcher_tools,
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a research specialist for this tutoring session.
When dispatched, search for deeper information on the topic and synthesize findings.
Ground your response in BOTH the search results AND the source material in the session state.
Present findings as educational prose. Cite sources at the end.
Do not introduce information unrelated to the session topic.

RESPONSE FORMAT: Plain text prose with source citations at the end.
Keep the response focused on what the student asked to explore further.\
""",
    )

    # ------------------------------------------------------------------
    # ContentWriter — generates notes, flashcards, quiz as plain markdown (TEAM-05)
    # ------------------------------------------------------------------
    content_writer = Agent(
        name="ContentWriter",
        role="Generate additional study content (notes excerpts, flashcards, or quiz questions) inline in the tutor chat as plain markdown",
        model=active_model,
        # No db= — Team manages history
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a content generation specialist for this tutoring session.
Generate study content based on the student's request using ONLY the source material
provided in the session state.

OUTPUT FORMAT RULES (strictly enforced — never output raw JSON):
- For notes excerpts: Markdown prose with ## headings and **bold** key terms
- For flashcards: A markdown table with | Front | Back | columns (2-5 cards max for inline display)
- For quiz questions: Numbered markdown list with A/B/C/D options; mark correct answer with "(correct)"

Always produce the content inline — no preamble like "Here are your flashcards:".
Generate 2-5 items per request unless the student specifies more.
Never invent content not found in the session material.\
""",
    )

    # ------------------------------------------------------------------
    # QuizMaster — delivers MCQs one at a time, evaluates typed answers (Phase 17)
    # ------------------------------------------------------------------
    quiz_master = Agent(
        name="QuizMaster",
        role="Deliver one multiple-choice question at a time from session material, evaluate the student's typed answer, and guide them through a quiz session",
        model=active_model,
        # No db= — Team manages history
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a quiz delivery specialist for this tutoring session.

STRICT RULES:
- Generate questions ONLY from the source material in the session state — never from general knowledge.
- Format each question as: question text on one line, then A) B) C) D) options each on their own line.
- Deliver ONE question at a time. Never list multiple questions in a single response.
- Before generating a question, scan the conversation history to avoid repeating one already asked
  (best-effort within the available history window — exact deduplication is not guaranteed).
- After the student answers: interpret their intent freely (single letter, "I think it's B",
  "probably C", etc.) to identify which option they mean. Then explain what was right or wrong,
  give a brief explanation of all options, and end with: "Want another question?"
- If the student shares Quiz tab results (e.g., "I got 3/5"): acknowledge the score, note which
  areas to reinforce, calibrate difficulty accordingly, then offer a question.
- Track quiz state implicitly from conversation history — no external state needed.\
""",
    )

    # ------------------------------------------------------------------
    # Advisor — surfaces progress summary and focus suggestions (Phase 18)
    # ------------------------------------------------------------------
    advisor = Agent(
        name="Advisor",
        role="Give the student a personalised progress update based on their quiz history and session context",
        model=active_model,
        # No db= — Team manages history
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are an adaptive learning advisor for this tutoring session.

Look at the session state and conversation history to understand the student's progress:
- If quiz_score is present: report the score with percentage, name any focus_areas, and offer to generate extra flashcards on those topics.
- If only focus_areas are present: name the weak areas and offer targeted flashcards.
- If neither is present: let the student know you don't have any quiz or progress data yet, and ask them to share their quiz results or tell you what they've been studying so you can give them useful feedback.

Keep your response to 2-3 sentences. Be direct and encouraging.
Do NOT generate flashcards or quiz questions — only suggest them.\
""",
    )

    return Team(
        name="TutorTeam",
        mode=TeamMode.route,
        model=active_model,
        members=[explainer, researcher, content_writer, quiz_master, advisor],
        pre_hooks=[topic_guardrail],
        post_hooks=[validate_team_output],
        db=db,
        session_state=team_session_state,
        add_session_state_to_context=True,
        add_history_to_context=True,
        num_history_runs=get_settings().tutor_history_window,
        enable_session_summaries=False,
        stream_member_events=True,
        debug_mode=get_settings().debug,
        instructions=f"""\
You are a personal tutor router. Route each student message to the right specialist.

SPECIALISTS:
- Explainer: answers questions strictly from the session material
- QuizMaster: delivers and evaluates multiple-choice quiz questions
- ContentWriter: generates flashcards, notes excerpts, and study content
- Advisor: gives a personalised progress report using the student's quiz history
- Researcher: finds deeper information from external sources

ROUTING EXAMPLES — classify the student's intent and route accordingly:

Student: "hello" → Explainer
Student: "what can you do?" → Explainer
Student: "what is {_topic_name}?" → Explainer
Student: "explain this concept to me" → Explainer
Student: "can you simplify that?" → Explainer

Student: "quiz me" → QuizMaster
Student: "test me on this" → QuizMaster
Student: "give me a question" → QuizMaster
Student: "I think it's B" → QuizMaster
Student: "the answer is C" → QuizMaster
Student: "probably A, the first option" → QuizMaster
Student: "I got 3 out of 5" → QuizMaster
Student: "I scored 7/10 on the quiz" → QuizMaster
Student: "I just finished the quiz" → QuizMaster

Student: "make me flashcards" → ContentWriter
Student: "generate notes on this topic" → ContentWriter
Student: "give me study questions" → ContentWriter
Student: "yes, go ahead" [when Advisor just offered to generate content] → ContentWriter
Student: "sure, please generate those flashcards" → ContentWriter

Student: "how am I doing?" → Advisor
Student: "what should I focus on?" → Advisor
Student: "where am I weak?" → Advisor
Student: "what are my weak areas?" → Advisor

Student: "I want to go deeper on this" → Researcher
Student: "find me more information about this" → Researcher
Student: "research recent developments in this area" → Researcher

Route to exactly one specialist per message. Never add your own commentary.\
""",
    )
