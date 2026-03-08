from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Literal


TutoringType = Literal["micro_learning", "teaching_a_kid", "advanced"]

SessionType = Literal["url", "topic"]


class SessionRequest(BaseModel):
    url: Optional[HttpUrl] = None
    paste_text: Optional[str] = None
    topic_description: Optional[str] = None
    tutoring_type: TutoringType
    focus_prompt: Optional[str] = None
    generate_flashcards: bool = False
    generate_quiz: bool = False

    model_config = {"str_strip_whitespace": True}


class Flashcard(BaseModel):
    front: str
    back: str


class QuizQuestion(BaseModel):
    question: str
    options: List[str]      # exactly 4 options
    answer_index: int        # 0-3, index into options


class SessionResult(BaseModel):
    session_id: str
    source_title: str
    tutoring_type: TutoringType
    session_type: SessionType = "url"
    sources: Optional[List[str]] = None
    notes: str               # markdown string
    flashcards: List[Flashcard]
    quiz: List[QuizQuestion]
    errors: Optional[dict] = None  # per-section errors e.g. {"flashcards": "...", "quiz": "..."}
    chat_intro: str = ""
