from pydantic import BaseModel
from typing import List, Literal


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    message: str
    tutoring_type: Literal["micro_learning", "teaching_a_kid", "advanced"]
    history: List[ChatMessage] = []
    session_id: str  # required; router loads notes from SQLite using this ID

    model_config = {"str_strip_whitespace": True}
