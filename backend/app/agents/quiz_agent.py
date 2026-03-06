from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS


def build_quiz_agent(tutoring_type: str, db: SqliteDb | None = None) -> Agent:
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="QuizAgent",
        model=get_model(),
        db=db,
        telemetry=True,
        instructions=f"""{persona}

Generate a multiple-choice quiz from the provided study content.
Return ONLY a JSON array with no markdown fences, no explanation, no preamble.
Format exactly:
[
  {{
    "question": "Question text",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer_index": 0
  }},
  ...
]
Rules:
- Exactly 4 options per question (the options array must have exactly 4 items)
- answer_index is the 0-based index of the correct option
- Generate 8-10 questions covering different concepts
- Adapt vocabulary and difficulty to match your role above.""",
    )
