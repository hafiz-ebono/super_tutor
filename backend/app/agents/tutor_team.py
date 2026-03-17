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
  Adaptive data (quiz_score, focus_areas) is NOT persisted to session_state; the Advisor
  reads progress signals directly from conversation history instead.
- Conversation history is managed at the Team level ONLY. Member agents do NOT get their
  own db= or add_history_to_context=True — that would create duplicate/conflicting session rows.
- TeamMode.route: coordinator uses transfer_to_X tools; the matched member's response is
  returned directly to the user with no coordinator wrapping or synthesis step.
  This preserves the original user message as-is to the member — critical for QuizMaster
  so it sees "quiz me" (not a coordinator task description) and correctly asks one question
  then waits, rather than generating a complete self-contained interaction.
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
You are a tutoring specialist for this session.

GREETINGS ("hello", "hi", "what can you do?", "help"):
Respond warmly in 1-2 sentences. Introduce yourself as the personal tutor and tell the
student they can ask questions about the material, get tested with quiz questions, or
generate flashcards and study notes — all grounded in this session's content.

CONTENT QUESTIONS:
Answer ONLY from the source material provided in the session state. Do not use outside
knowledge. Answer directly — do NOT start your reply with any disclaimer. Only if the
question genuinely cannot be answered from the material, say:
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
        id="contentwriter",
        role="Generate additional study content (notes excerpts, flashcards, or quiz questions) inline in the tutor chat as plain markdown",
        model=active_model,
        # No db= — Team manages history
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a content generation specialist for this tutoring session.
Generate study content based on the student's request using ONLY the source material
provided in the session state.

OUTPUT FORMAT — output ONLY the content, no preamble, no "Here are your flashcards:":
- For notes excerpts: Markdown prose with ## headings and **bold** key terms
- For flashcards: A markdown table EXACTLY in this format — first row is the header,
  second row is the separator, then 2-5 data rows:
  | Front | Back |
  | --- | --- |
  | Question or term | Answer or definition |
- For quiz questions: Numbered markdown list with A/B/C/D options; mark correct answer with "(correct)"
- Never output raw JSON.

Generate 2-5 items per request unless the student specifies more.
Never invent content not found in the session material.\
""",
    )

    # ------------------------------------------------------------------
    # QuizMaster — delivers MCQs one at a time, evaluates typed answers (Phase 17)
    # ------------------------------------------------------------------
    quiz_master = Agent(
        name="QuizMaster",
        id="quizmaster",
        role="Deliver one multiple-choice question at a time from session material, evaluate the student's typed answer, and guide them through a quiz session",
        model=active_model,
        # No db= — Team manages history
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions="""\
You are a quiz delivery specialist for this tutoring session.
Go straight to the task. Never say "I can't start the quiz directly" or "I don't have
access to" — just deliver or evaluate a question immediately.

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
Go straight to the task. Never say "I can't access" or "I don't have data" — work
with whatever is in the conversation history.

Look at the conversation history to understand the student's progress:
- If the student shared quiz results (e.g., "I got 3/5", wrong questions listed): summarise
  their performance, name the weak areas by topic, and offer to generate targeted flashcards.
- If the student has been answering quiz questions in this session: observe their Q&A history,
  note which topics they struggled with, and offer targeted practice on those areas.
- If there is no quiz activity in the conversation yet: encourage the student to try the quiz
  tab or ask to be tested, then come back for personalised guidance.

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
You are a personal tutor coordinator. Your job is to understand what the student needs
and delegate to the right specialist. ALWAYS delegate — never answer directly yourself.

SPECIALISTS AND WHEN TO USE THEM:
- Explainer: student asks a question about the material, wants a concept clarified, or says hello
- QuizMaster: student wants to be tested, says "quiz me", answers a quiz question, or shares quiz tab results
- ContentWriter: student asks for flashcards, notes, or study content; or accepts an Advisor suggestion
- Advisor: student asks how they are doing, wants to know their weak areas, or asks what to focus on
- Researcher: student wants to go deeper, find external information, or research the topic further

ROUTING EXAMPLES — pick the specialist whose role matches the student's intent:

"hello" → Explainer
"what can you do?" → Explainer
"what is {_topic_name}?" → Explainer
"explain this concept to me" → Explainer
"can you simplify that?" → Explainer

"quiz me" → QuizMaster
"test me on this" → QuizMaster
"give me a question" → QuizMaster
"I think it's B" → QuizMaster
"the answer is C" → QuizMaster
"probably A, the first option" → QuizMaster
"I got 3 out of 5" → QuizMaster
"I scored 7/10 on the quiz" → QuizMaster
"I just finished the quiz" → QuizMaster

"make me flashcards" → ContentWriter
"generate notes on this topic" → ContentWriter
"give me study questions" → ContentWriter
"yes, go ahead" [when Advisor just offered to generate content] → ContentWriter
"sure, please generate those flashcards" → ContentWriter

"how am I doing?" → Advisor
"what should I focus on?" → Advisor
"where am I weak?" → Advisor
"what are my weak areas?" → Advisor

"I want to go deeper on this" → Researcher
"find me more information about this" → Researcher
"research recent developments in this area" → Researcher

CRITICAL RULES:
- Delegate to exactly one specialist per message.
- Do NOT add your own commentary before or after the specialist's response.
- Do NOT say "I'm routing you to..." or explain your decision — just delegate silently.
- Do NOT say you lack tools or capabilities — you always have specialists available.\
""",
    )
