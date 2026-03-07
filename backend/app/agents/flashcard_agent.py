from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS


def build_flashcard_agent(tutoring_type: str, db: SqliteDb | None = None) -> Agent:
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="FlashcardAgent",
        model=get_model(),
        db=db,
        enable_session_summaries=True,
        instructions=f"""{persona}

Generate flashcards from the provided study content.
Return ONLY a JSON array with no markdown fences, no explanation, no preamble.
Format exactly:
[
  {{"front": "Question or term", "back": "Answer or definition"}},
  ...
]
Generate 8-12 flashcards covering the key concepts.
Adapt vocabulary and complexity to match your role above.""",
    )
