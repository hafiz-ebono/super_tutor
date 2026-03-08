"""
Tests for Pydantic model changes introduced in Task 2:
- SessionRequest: generate_flashcards and generate_quiz opt-in flags
- SessionResult: chat_intro greeting field
- ChatStreamRequest: notes removed, session_id made required
"""
import pytest
from pydantic import ValidationError

from app.models.session import SessionRequest, SessionResult, Flashcard, QuizQuestion
from app.models.chat import ChatStreamRequest


# ---------------------------------------------------------------------------
# SessionRequest
# ---------------------------------------------------------------------------

def test_session_request_defaults():
    """Minimal valid SessionRequest must default both opt-in flags to False."""
    req = SessionRequest(tutoring_type="micro_learning")
    assert req.generate_flashcards is False
    assert req.generate_quiz is False


def test_session_request_opt_in_flags():
    """Explicitly enabling both opt-in flags must be reflected on the model."""
    req = SessionRequest(
        tutoring_type="advanced",
        generate_flashcards=True,
        generate_quiz=True,
    )
    assert req.generate_flashcards is True
    assert req.generate_quiz is True


# ---------------------------------------------------------------------------
# SessionResult
# ---------------------------------------------------------------------------

def _make_session_result(**overrides):
    """Helper: build a minimal valid SessionResult."""
    defaults = dict(
        session_id="sess-123",
        source_title="Test Source",
        tutoring_type="micro_learning",
        notes="## Notes\n- point one",
        flashcards=[Flashcard(front="Q", back="A")],
        quiz=[QuizQuestion(question="Q?", options=["A", "B", "C", "D"], answer_index=0)],
    )
    defaults.update(overrides)
    return SessionResult(**defaults)


def test_session_result_chat_intro_default():
    """SessionResult must default chat_intro to an empty string."""
    result = _make_session_result()
    assert result.chat_intro == ""


def test_session_result_with_chat_intro():
    """SessionResult must store an explicit chat_intro value."""
    result = _make_session_result(chat_intro="Hello! Ready to study?")
    assert result.chat_intro == "Hello! Ready to study?"


# ---------------------------------------------------------------------------
# ChatStreamRequest
# ---------------------------------------------------------------------------

def test_chat_stream_request_no_notes():
    """ChatStreamRequest must not declare a 'notes' field."""
    assert "notes" not in ChatStreamRequest.model_fields


def test_chat_stream_request_session_id_required():
    """ChatStreamRequest must raise ValidationError when session_id is omitted."""
    with pytest.raises(ValidationError):
        ChatStreamRequest(
            message="What is photosynthesis?",
            tutoring_type="micro_learning",
        )
