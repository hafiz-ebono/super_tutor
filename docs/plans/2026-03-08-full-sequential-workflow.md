# Full Sequential Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the Agno Workflow to a full sequential pipeline (research → notes → flashcards → quiz → title) with opt-in generation flags, source content persisted in session state, and the chat agent loading notes from SQLite instead of the request body.

**Architecture:** Add five step executors to `session_workflow.py` (research_step, updated notes_step, flashcards_step, quiz_step, title_step). The workflow step list is built conditionally per request. The chat router is updated to load notes from SQLite via `session_id`. Frontend adds opt-in checkboxes and removes notes from the chat request body.

**Tech Stack:** Python 3.11, FastAPI, Agno >= 2.5.7, SQLite (SqliteDb), Next.js 14, TypeScript, Tailwind CSS.

**Design doc:** `docs/plans/2026-03-08-full-sequential-workflow-design.md`

---

## Task 1: Add chat intro strings to personas

**Files:**
- Modify: `backend/app/agents/personas.py`

**Step 1: Add CHAT_INTROS dict below PERSONAS**

```python
CHAT_INTROS: dict[str, str] = {
    "micro_learning": "Session assistant here. Ask me anything — I'll keep it short.",
    "teaching_a_kid": "Hi! I'm your study buddy for this session! What would you like to understand?",
    "advanced": "I'm your session tutor. I have full context of this material — ask me anything, including edge cases and nuance.",
}
```

**Step 2: Commit**

```bash
git add backend/app/agents/personas.py
git commit -m "feat: add CHAT_INTROS dict to personas"
```

---

## Task 2: Update Pydantic models

**Files:**
- Modify: `backend/app/models/session.py`
- Modify: `backend/app/models/chat.py`

**Step 1: Write failing test for new SessionRequest fields**

Create `backend/tests/test_models.py`:

```python
from app.models.session import SessionRequest, SessionResult
from app.models.chat import ChatStreamRequest


def test_session_request_defaults_generate_flags_to_false():
    req = SessionRequest(tutoring_type="micro_learning", url="https://example.com")
    assert req.generate_flashcards is False
    assert req.generate_quiz is False


def test_session_request_accepts_generate_flags():
    req = SessionRequest(
        tutoring_type="micro_learning",
        url="https://example.com",
        generate_flashcards=True,
        generate_quiz=True,
    )
    assert req.generate_flashcards is True
    assert req.generate_quiz is True


def test_session_result_has_chat_intro():
    result = SessionResult(
        session_id="abc",
        source_title="Test",
        tutoring_type="micro_learning",
        notes="# Notes",
        flashcards=[],
        quiz=[],
        chat_intro="Session assistant here.",
    )
    assert result.chat_intro == "Session assistant here."


def test_chat_stream_request_no_notes_field():
    req = ChatStreamRequest(
        message="hello",
        tutoring_type="micro_learning",
        history=[],
        session_id="abc123",
    )
    assert not hasattr(req, "notes")
    assert req.session_id == "abc123"
```

**Step 2: Run test to confirm it fails**

```bash
cd backend && python -m pytest tests/test_models.py -v
```
Expected: FAIL — `generate_flashcards` field not found, `chat_intro` not found.

**Step 3: Update `backend/app/models/session.py`**

```python
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Literal


TutoringType = Literal["micro_learning", "teaching_a_kid", "advanced"]
SessionType = Literal["url", "topic", "paste"]


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
    notes: str
    flashcards: List[Flashcard]
    quiz: List[QuizQuestion]
    errors: Optional[dict] = None
    chat_intro: str = ""
```

**Step 4: Update `backend/app/models/chat.py`**

Remove `notes` field, make `session_id` required:

```python
from pydantic import BaseModel
from typing import List, Literal, Optional


TutoringType = Literal["micro_learning", "teaching_a_kid", "advanced"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    message: str
    tutoring_type: TutoringType
    history: List[ChatMessage] = []
    session_id: str
```

**Step 5: Run tests — expect pass**

```bash
python -m pytest tests/test_models.py -v
```
Expected: all 4 PASS.

**Step 6: Commit**

```bash
git add backend/app/models/session.py backend/app/models/chat.py backend/tests/test_models.py
git commit -m "feat: add generate_flashcards/quiz flags to SessionRequest, chat_intro to SessionResult, remove notes from ChatStreamRequest"
```

---

## Task 3: Add research_step to session_workflow.py

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`

**Step 1: Write failing test**

Add to a new file `backend/tests/test_workflow_steps.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from agno.workflow.types import StepInput


def _make_step_input(**kwargs):
    si = MagicMock(spec=StepInput)
    si.additional_data = kwargs
    return si


def test_research_step_writes_source_content_to_session_state():
    from app.workflows.session_workflow import research_step
    mock_result = MagicMock()
    mock_result.content = "Researched content about topic"
    mock_result.sources = ["https://example.com"]

    with patch("app.workflows.session_workflow.run_research", return_value=mock_result):
        session_state = {}
        step_input = _make_step_input(
            topic_description="quantum computing",
            focus_prompt="",
            session_id="test-123",
            traces_db=None,
        )
        from app.workflows.session_workflow import research_step
        output = research_step(step_input, session_state)

    assert session_state["source_content"] == "Researched content about topic"
    assert session_state["sources"] == ["https://example.com"]
    assert output.content == "Researched content about topic"


def test_research_step_raises_on_empty_content():
    from app.workflows.session_workflow import research_step
    mock_result = MagicMock()
    mock_result.content = ""
    mock_result.sources = []

    with patch("app.workflows.session_workflow.run_research", return_value=mock_result):
        session_state = {}
        step_input = _make_step_input(
            topic_description="quantum computing",
            focus_prompt="",
            session_id="test-123",
            traces_db=None,
        )
        with pytest.raises(RuntimeError, match="Research returned no content"):
            research_step(step_input, session_state)
```

**Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_workflow_steps.py::test_research_step_writes_source_content_to_session_state -v
```
Expected: ImportError — `research_step` not defined.

**Step 3: Add `research_step` to `session_workflow.py`**

Add after the existing imports, before `notes_step`. Also import `run_research` at the top if not already imported:

```python
from app.agents.research_agent import run_research
```

Then add the step function:

```python
def research_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Runs ResearchAgent for topic-mode sessions.
    Fatal step — raises RuntimeError if research returns no content.
    IMPORTANT: Runs inside asyncio.to_thread — do NOT use await.
    """
    topic_description = step_input.additional_data.get("topic_description", "")
    focus_prompt = step_input.additional_data.get("focus_prompt", "")
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("traces_db")

    logger.info("Workflow step start — step=research topic=%r", topic_description[:80])
    _t = time.perf_counter()
    try:
        result = run_research(
            topic_description,
            focus_prompt=focus_prompt,
            session_id=session_id,
            db=traces_db,
        )
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in research_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Research topic rejected by input guardrail. Please rephrase your topic."
        ) from e
    except Exception as e:
        logger.error("Research failed in research_step — error=%s", e, exc_info=True)
        raise RuntimeError(f"Research failed: {e}") from e

    logger.info("Workflow step done — step=research elapsed=%.2fs", time.perf_counter() - _t)

    content = result.content or ""
    if len(content.strip()) < 100:
        raise RuntimeError(
            "Research returned no content. Please try a more specific topic."
        )

    session_state["source_content"] = content
    session_state["sources"] = result.sources or []
    return StepOutput(content=content)
```

**Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_workflow_steps.py::test_research_step_writes_source_content_to_session_state tests/test_workflow_steps.py::test_research_step_raises_on_empty_content -v
```
Expected: both PASS.

**Step 5: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: add research_step to session workflow"
```

---

## Task 4: Update notes_step to read from session_state

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`
- Modify: `backend/tests/test_workflow_steps.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_workflow_steps.py`:

```python
def test_notes_step_reads_source_content_from_session_state():
    """For topic path: source_content is already in session_state from research_step."""
    from app.workflows.session_workflow import notes_step
    mock_result = MagicMock()
    mock_result.content = "# Notes\n\nThis is a comprehensive note " * 10

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_notes_agent", return_value=MagicMock()):
            session_state = {"source_content": "Pre-researched content about the topic"}
            step_input = _make_step_input(
                source_content="",  # empty — should be ignored
                tutoring_type="micro_learning",
                session_type="topic",
                session_id="test-123",
                traces_db=None,
                focus_prompt="",
            )
            notes_step(step_input, session_state)

    # source_content in session_state must remain from research_step
    assert session_state["source_content"] == "Pre-researched content about the topic"
    assert "notes" in session_state


def test_notes_step_reads_source_content_from_additional_data():
    """For URL/paste path: source_content comes from additional_data."""
    from app.workflows.session_workflow import notes_step
    mock_result = MagicMock()
    mock_result.content = "# Notes\n\nThis is a comprehensive note " * 10

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_notes_agent", return_value=MagicMock()):
            session_state = {}  # empty — URL path, no research_step ran
            step_input = _make_step_input(
                source_content="Extracted article text from URL",
                tutoring_type="micro_learning",
                session_type="url",
                session_id="test-123",
                traces_db=None,
                focus_prompt="",
            )
            notes_step(step_input, session_state)

    assert session_state["source_content"] == "Extracted article text from URL"
    assert "notes" in session_state


def test_notes_step_sets_chat_intro():
    from app.workflows.session_workflow import notes_step
    mock_result = MagicMock()
    mock_result.content = "# Notes\n\nThis is a comprehensive note " * 10

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_notes_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content"}
            step_input = _make_step_input(
                source_content="",
                tutoring_type="advanced",
                session_type="url",
                session_id="test-123",
                traces_db=None,
                focus_prompt="",
            )
            notes_step(step_input, session_state)

    assert "chat_intro" in session_state
    assert "tutor" in session_state["chat_intro"].lower()
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_workflow_steps.py::test_notes_step_reads_source_content_from_session_state -v
```
Expected: FAIL — `source_content` not in session_state after call.

**Step 3: Rewrite `notes_step` in `session_workflow.py`**

Replace the existing `notes_step` function entirely:

```python
def notes_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates study notes from source_content.
    For topic path: reads source_content from session_state (set by research_step).
    For URL/paste path: reads source_content from additional_data and writes it to session_state.
    Fatal step — raises RuntimeError if notes are too short.
    IMPORTANT: Runs inside asyncio.to_thread — do NOT use await.
    """
    settings = get_settings()

    # Topic path: source_content already in session_state from research_step.
    # URL/paste path: source_content arrives via additional_data.
    source_content = session_state.get("source_content") or step_input.additional_data.get("source_content", "")
    tutoring_type = step_input.additional_data.get("tutoring_type", "micro_learning")
    session_type = step_input.additional_data.get("session_type", "url")
    focus_prompt = step_input.additional_data.get("focus_prompt", "")
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("traces_db")

    input_text = (
        f"Content:\n{source_content}\n\nFocus on: {focus_prompt}"
        if focus_prompt
        else f"Content:\n{source_content}"
    )

    notes_agent = build_notes_agent(tutoring_type, db=traces_db)
    logger.info("Workflow step start — step=notes tutoring_type=%s", tutoring_type)
    _t = time.perf_counter()
    try:
        notes_result = run_with_retry(
            notes_agent.run,
            input_text,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in notes_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Content rejected by input guardrail. If this is unexpected, try rephrasing your input."
        ) from e
    logger.info("Workflow step done — step=notes elapsed=%.2fs", time.perf_counter() - _t)

    notes = notes_result.content or ""
    if len(notes.strip()) < 100:
        raise RuntimeError(
            f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
        )

    # Persist all fields to session_state — Agno saves to SQLite in finally block
    session_state["source_content"] = source_content
    session_state["notes"] = notes
    session_state["tutoring_type"] = tutoring_type
    session_state["session_type"] = session_type
    session_state["sources"] = session_state.get("sources", [])
    session_state["chat_intro"] = CHAT_INTROS.get(tutoring_type, "")

    return StepOutput(content=notes)
```

Also add the import at the top of the file:

```python
from app.agents.personas import CHAT_INTROS
```

**Step 4: Run all notes tests — expect pass**

```bash
python -m pytest tests/test_workflow_steps.py -k "notes_step" -v
```
Expected: all 3 PASS.

**Step 5: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: update notes_step to read source_content from session_state and set chat_intro"
```

---

## Task 5: Add flashcards_step

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`
- Modify: `backend/tests/test_workflow_steps.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_workflow_steps.py`:

```python
def test_flashcards_step_parses_json_into_session_state():
    from app.workflows.session_workflow import flashcards_step
    mock_result = MagicMock()
    mock_result.content = '[{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]'

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_flashcard_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content", "tutoring_type": "micro_learning"}
            step_input = _make_step_input(session_id="test-123", traces_db=None)
            flashcards_step(step_input, session_state)

    assert session_state["flashcards"] == [{"front": "Q1", "back": "A1"}, {"front": "Q2", "back": "A2"}]


def test_flashcards_step_non_fatal_on_bad_json():
    from app.workflows.session_workflow import flashcards_step
    mock_result = MagicMock()
    mock_result.content = "not valid json"

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_flashcard_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content", "tutoring_type": "micro_learning"}
            step_input = _make_step_input(session_id="test-123", traces_db=None)
            # Should NOT raise — non-fatal step
            flashcards_step(step_input, session_state)

    assert session_state["flashcards"] == []
    assert "flashcards" in session_state.get("errors", {})


def test_flashcards_step_non_fatal_on_agent_exception():
    from app.workflows.session_workflow import flashcards_step
    with patch("app.workflows.session_workflow.run_with_retry", side_effect=RuntimeError("LLM error")):
        with patch("app.workflows.session_workflow.build_flashcard_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content", "tutoring_type": "micro_learning"}
            step_input = _make_step_input(session_id="test-123", traces_db=None)
            # Should NOT raise
            flashcards_step(step_input, session_state)

    assert session_state["flashcards"] == []
    assert "flashcards" in session_state.get("errors", {})
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_workflow_steps.py -k "flashcards_step" -v
```
Expected: ImportError — `flashcards_step` not defined.

**Step 3: Add `flashcards_step` to `session_workflow.py`**

Add after `notes_step`:

```python
def flashcards_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates flashcards from source_content.
    Non-fatal — on any failure writes to session_state["errors"]["flashcards"] and continues.
    IMPORTANT: Runs inside asyncio.to_thread — do NOT use await.
    """
    settings = get_settings()
    source_content = session_state.get("source_content", "")
    tutoring_type = session_state.get("tutoring_type", "micro_learning")
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("traces_db")

    if not session_state.get("errors"):
        session_state["errors"] = {}

    logger.info("Workflow step start — step=flashcards tutoring_type=%s", tutoring_type)
    _t = time.perf_counter()
    try:
        agent = build_flashcard_agent(tutoring_type, db=traces_db)
        result = run_with_retry(
            agent.run,
            f"Content:\n{source_content}",
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )
        raw = result.content or "[]"
        flashcards = _parse_json_safe(raw, [])
        if not flashcards:
            raise ValueError(f"Flashcard JSON parse returned empty list — raw={raw[:200]!r}")
        session_state["flashcards"] = flashcards
        logger.info(
            "Workflow step done — step=flashcards elapsed=%.2fs count=%d",
            time.perf_counter() - _t,
            len(flashcards),
        )
    except Exception as e:
        logger.warning("Flashcards step failed (non-fatal) — error=%s", e, exc_info=True)
        session_state["flashcards"] = []
        session_state["errors"]["flashcards"] = str(e)

    return StepOutput(content=str(session_state.get("flashcards", [])))
```

**Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_workflow_steps.py -k "flashcards_step" -v
```
Expected: all 3 PASS.

**Step 5: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: add flashcards_step to session workflow (non-fatal)"
```

---

## Task 6: Add quiz_step

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`
- Modify: `backend/tests/test_workflow_steps.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_workflow_steps.py`:

```python
def test_quiz_step_parses_json_into_session_state():
    from app.workflows.session_workflow import quiz_step
    mock_result = MagicMock()
    mock_result.content = '[{"question": "Q?", "options": ["A","B","C","D"], "answer_index": 0}]'

    with patch("app.workflows.session_workflow.run_with_retry", return_value=mock_result):
        with patch("app.workflows.session_workflow.build_quiz_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content", "tutoring_type": "micro_learning"}
            step_input = _make_step_input(session_id="test-123", traces_db=None)
            quiz_step(step_input, session_state)

    assert len(session_state["quiz"]) == 1
    assert session_state["quiz"][0]["question"] == "Q?"


def test_quiz_step_non_fatal_on_failure():
    from app.workflows.session_workflow import quiz_step
    with patch("app.workflows.session_workflow.run_with_retry", side_effect=RuntimeError("LLM error")):
        with patch("app.workflows.session_workflow.build_quiz_agent", return_value=MagicMock()):
            session_state = {"source_content": "Some content", "tutoring_type": "micro_learning"}
            step_input = _make_step_input(session_id="test-123", traces_db=None)
            quiz_step(step_input, session_state)

    assert session_state["quiz"] == []
    assert "quiz" in session_state.get("errors", {})
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_workflow_steps.py -k "quiz_step" -v
```
Expected: ImportError — `quiz_step` not defined.

**Step 3: Add `quiz_step` to `session_workflow.py`**

Add after `flashcards_step`:

```python
def quiz_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates a multiple-choice quiz from source_content.
    Non-fatal — on any failure writes to session_state["errors"]["quiz"] and continues.
    IMPORTANT: Runs inside asyncio.to_thread — do NOT use await.
    """
    settings = get_settings()
    source_content = session_state.get("source_content", "")
    tutoring_type = session_state.get("tutoring_type", "micro_learning")
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("traces_db")

    if not session_state.get("errors"):
        session_state["errors"] = {}

    logger.info("Workflow step start — step=quiz tutoring_type=%s", tutoring_type)
    _t = time.perf_counter()
    try:
        agent = build_quiz_agent(tutoring_type, db=traces_db)
        result = run_with_retry(
            agent.run,
            f"Content:\n{source_content}",
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )
        raw = result.content or "[]"
        quiz = _parse_json_safe(raw, [])
        if not quiz:
            raise ValueError(f"Quiz JSON parse returned empty list — raw={raw[:200]!r}")
        session_state["quiz"] = quiz
        logger.info(
            "Workflow step done — step=quiz elapsed=%.2fs count=%d",
            time.perf_counter() - _t,
            len(quiz),
        )
    except Exception as e:
        logger.warning("Quiz step failed (non-fatal) — error=%s", e, exc_info=True)
        session_state["quiz"] = []
        session_state["errors"]["quiz"] = str(e)

    return StepOutput(content=str(session_state.get("quiz", [])))
```

**Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_workflow_steps.py -k "quiz_step" -v
```
Expected: both PASS.

**Step 5: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: add quiz_step to session workflow (non-fatal)"
```

---

## Task 7: Add title_step

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`
- Modify: `backend/tests/test_workflow_steps.py`

**Step 1: Write failing test**

Add to `backend/tests/test_workflow_steps.py`:

```python
def test_title_step_writes_title_to_session_state():
    from app.workflows.session_workflow import title_step
    with patch("app.workflows.session_workflow._generate_title", return_value="Quantum Computing Basics"):
        session_state = {
            "source_content": "Long article text...",
            "notes": "# Notes\n\nSome notes",
        }
        step_input = _make_step_input(
            title_input="Quantum Computing",
            session_id="test-123",
            traces_db=None,
        )
        title_step(step_input, session_state)

    assert session_state["title"] == "Quantum Computing Basics"


def test_title_step_falls_back_to_extract_title_on_failure():
    from app.workflows.session_workflow import title_step
    with patch("app.workflows.session_workflow._generate_title", side_effect=Exception("LLM error")):
        session_state = {
            "source_content": "Long article text...",
            "notes": "# Quantum Physics\n\nSome notes",
        }
        step_input = _make_step_input(
            title_input="",
            session_id="test-123",
            traces_db=None,
        )
        title_step(step_input, session_state)

    assert session_state["title"] == "Quantum Physics"
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_workflow_steps.py -k "title_step" -v
```
Expected: ImportError — `title_step` not defined.

**Step 3: Add `title_step` to `session_workflow.py`**

Add after `quiz_step`:

```python
def title_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates a 3-5 word title from source_content.
    Non-fatal — falls back to _extract_title(notes) on any failure.
    IMPORTANT: Runs inside asyncio.to_thread — do NOT use await.
    """
    source_content = session_state.get("source_content", "")
    notes = session_state.get("notes", "")
    session_id = step_input.additional_data.get("session_id", "")
    title_input = step_input.additional_data.get("title_input", "")
    traces_db = step_input.additional_data.get("traces_db")

    logger.info("Workflow step start — step=title")
    try:
        title = _generate_title(
            title_input if title_input else source_content,
            fallback=title_input,
            db=traces_db,
            session_id=session_id,
        )
    except Exception as e:
        logger.warning("Title step failed (non-fatal), falling back — error=%s", e)
        title = _extract_title(notes)

    session_state["title"] = title
    logger.info("Workflow step done — step=title title=%r", title)
    return StepOutput(content=title)
```

**Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_workflow_steps.py -k "title_step" -v
```
Expected: both PASS.

**Step 5: Run full test suite to confirm nothing broken**

```bash
python -m pytest tests/ -v
```
Expected: all tests PASS.

**Step 6: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: add title_step to session workflow (non-fatal with fallback)"
```

---

## Task 8: Rewrite build_session_workflow and run_session_workflow

**Files:**
- Modify: `backend/app/workflows/session_workflow.py`

**Step 1: Write failing tests**

Add to `backend/tests/test_workflow_steps.py`:

```python
def test_build_session_workflow_topic_path_includes_research_step():
    from app.workflows.session_workflow import build_session_workflow
    from agno.db.sqlite import SqliteDb
    db = MagicMock(spec=SqliteDb)
    wf = build_session_workflow(
        session_id="abc",
        session_db=db,
        session_type="topic",
        generate_flashcards=False,
        generate_quiz=False,
    )
    step_names = [s.name for s in wf.steps]
    assert step_names[0] == "research"
    assert "notes" in step_names
    assert "flashcards" not in step_names
    assert "quiz" not in step_names
    assert "title" in step_names


def test_build_session_workflow_url_path_skips_research_step():
    from app.workflows.session_workflow import build_session_workflow
    from agno.db.sqlite import SqliteDb
    db = MagicMock(spec=SqliteDb)
    wf = build_session_workflow(
        session_id="abc",
        session_db=db,
        session_type="url",
        generate_flashcards=False,
        generate_quiz=False,
    )
    step_names = [s.name for s in wf.steps]
    assert "research" not in step_names
    assert step_names[0] == "notes"


def test_build_session_workflow_includes_optional_steps_when_opted_in():
    from app.workflows.session_workflow import build_session_workflow
    from agno.db.sqlite import SqliteDb
    db = MagicMock(spec=SqliteDb)
    wf = build_session_workflow(
        session_id="abc",
        session_db=db,
        session_type="url",
        generate_flashcards=True,
        generate_quiz=True,
    )
    step_names = [s.name for s in wf.steps]
    assert step_names == ["notes", "flashcards", "quiz", "title"]
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_workflow_steps.py -k "build_session_workflow" -v
```
Expected: FAIL — `build_session_workflow` doesn't accept new params.

**Step 3: Replace `build_session_workflow` and `run_session_workflow` in `session_workflow.py`**

Replace both functions:

```python
def build_session_workflow(
    session_id: str,
    session_db: SqliteDb,
    session_type: str = "url",
    generate_flashcards: bool = False,
    generate_quiz: bool = False,
) -> Workflow:
    """
    Per-request factory. Never reuse across requests.
    Builds conditional step list based on session_type and opt-in flags.
    """
    steps = []

    if session_type == "topic":
        steps.append(Step(name="research", executor=research_step))

    steps.append(Step(name="notes", executor=notes_step))

    if generate_flashcards:
        steps.append(Step(name="flashcards", executor=flashcards_step))

    if generate_quiz:
        steps.append(Step(name="quiz", executor=quiz_step))

    steps.append(Step(name="title", executor=title_step))

    return Workflow(
        id="session-workflow",
        name="Session Workflow",
        steps=steps,
        db=session_db,
        session_id=session_id,
    )


async def run_session_workflow(
    session_id: str,
    source_content: str,
    tutoring_type: str,
    focus_prompt: str = "",
    url: str = "",
    session_type: str = "url",
    sources: list | None = None,
    title_input: str = "",
    topic_description: str = "",
    generate_flashcards: bool = False,
    generate_quiz: bool = False,
    traces_db: SqliteDb | None = None,
) -> AsyncGenerator[RunResponse, None]:
    """
    Async generator yielding RunResponse-compatible objects for the SSE router.
    Yields predicted progress events before starting the workflow thread,
    then yields the complete event with full session data.
    """
    # Yield predicted progress events upfront (reflects what steps will run)
    if session_type == "topic":
        yield RunResponse(content="Researching your topic...")
    yield RunResponse(content="Crafting your notes...")
    if generate_flashcards:
        yield RunResponse(content="Generating flashcards...")
    if generate_quiz:
        yield RunResponse(content="Generating quiz...")
    yield RunResponse(content="Finishing up...")

    workflow = build_session_workflow(
        session_id=session_id,
        session_db=_get_session_db(),
        session_type=session_type,
        generate_flashcards=generate_flashcards,
        generate_quiz=generate_quiz,
    )

    result = await asyncio.to_thread(
        workflow.run,
        additional_data={
            "source_content": source_content,
            "topic_description": topic_description,
            "tutoring_type": tutoring_type,
            "focus_prompt": focus_prompt,
            "session_type": session_type,
            "sources": sources or [],
            "session_id": session_id,
            "title_input": title_input,
            "traces_db": traces_db,
        },
        session_id=session_id,
    )

    # Read final session state from the workflow result's session
    session = workflow.get_session(session_id=session_id)
    state = session.session_state if session else {}

    yield RunResponse(
        event="workflow_completed",
        content={
            "source_title": state.get("title", title_input or url or "Untitled"),
            "tutoring_type": tutoring_type,
            "session_type": session_type,
            "sources": state.get("sources", sources or []),
            "notes": state.get("notes", ""),
            "flashcards": state.get("flashcards", []),
            "quiz": state.get("quiz", []),
            "errors": state.get("errors") or None,
            "chat_intro": state.get("chat_intro", ""),
        },
    )
```

**Step 4: Run all workflow tests**

```bash
python -m pytest tests/test_workflow_steps.py -v
```
Expected: all PASS.

**Step 5: Commit**

```bash
git add backend/app/workflows/session_workflow.py backend/tests/test_workflow_steps.py
git commit -m "feat: rebuild build_session_workflow and run_session_workflow with full conditional pipeline"
```

---

## Task 9: Update sessions.py router

**Files:**
- Modify: `backend/app/routers/sessions.py`

**Step 1: Update `event_generator` in `stream_session`**

Key changes:
- Remove the research block (now handled by `research_step`)
- Remove the `_generate_title` call (now handled by `title_step`)
- Pass `source_content`, `topic_description`, `generate_flashcards`, `generate_quiz` to `run_session_workflow`
- For topic path: pass `topic_description` to workflow; content passed as `""` (research_step fetches it)
- For URL/paste path: pass extracted/pasted text as `source_content`

Replace the entire `event_generator` inner function inside `stream_session`:

```python
async def event_generator() -> AsyncGenerator[dict, None]:
    url = params.get("url") or ""
    paste_text = params.get("paste_text") or ""
    topic_description = params.get("topic_description") or ""
    tutoring_type = params["tutoring_type"]
    focus_prompt = params.get("focus_prompt") or ""
    generate_flashcards = params.get("generate_flashcards", False)
    generate_quiz = params.get("generate_quiz", False)

    session_type = "url"
    source_content = ""
    sources = None
    title_input = ""

    # Input validation
    if topic_description and len(topic_description.strip()) < 10:
        yield {
            "event": "error",
            "data": json.dumps({"kind": "invalid_url", "message": "Topic description is too short. Please describe what you want to learn."}),
        }
        return

    try:
        if topic_description:
            session_type = "topic"
            title_input = topic_description
            source_content = ""  # research_step will populate source_content in session_state

            word_count = len(topic_description.split())
            if word_count < 3:
                yield {
                    "event": "warning",
                    "data": json.dumps({"message": "Your topic is quite broad — we'll do our best, but consider adding more detail."}),
                }
                await asyncio.sleep(0)

        elif paste_text:
            session_type = "paste"
            source_content = paste_text

        elif url:
            session_type = "url"
            yield {
                "event": "progress",
                "data": json.dumps({"message": "Reading the article..."}),
            }
            try:
                source_content = await extract_content(str(url))
            except ExtractionError as e:
                logger.warning("Extraction error — session_id=%s kind=%s", session_id, e.kind)
                yield {
                    "event": "error",
                    "data": json.dumps({"kind": e.kind, "message": e.message}),
                }
                return
        else:
            yield {
                "event": "error",
                "data": json.dumps({"kind": "invalid_url", "message": "No URL, text, or topic provided"}),
            }
            return

    except ExtractionError as e:
        yield {"event": "error", "data": json.dumps({"kind": e.kind, "message": e.message})}
        return

    # Run the full workflow pipeline
    try:
        async for response in run_session_workflow(
            session_id=session_id,
            source_content=source_content,
            tutoring_type=tutoring_type,
            focus_prompt=focus_prompt,
            url=str(params.get("url") or ""),
            session_type=session_type,
            sources=sources,
            title_input=title_input,
            topic_description=topic_description,
            generate_flashcards=generate_flashcards,
            generate_quiz=generate_quiz,
            traces_db=_get_traces_db(),
        ):
            event_name = getattr(response.event, "value", str(response.event)) if response.event else ""
            is_complete = "completed" in event_name or isinstance(response.content, dict)

            if is_complete and isinstance(response.content, dict):
                session_data = {"session_id": session_id, **response.content}
                logger.info("Stream complete — session_id=%s", session_id)
                yield {"event": "complete", "data": json.dumps(session_data)}
            elif isinstance(response.content, str):
                yield {"event": "progress", "data": json.dumps({"message": response.content})}

            await asyncio.sleep(0)

    except Exception as e:
        logger.error("Workflow error — session_id=%s error=%s", session_id, e, exc_info=True)
        user_msg = (
            "The AI is temporarily busy — please try again in a moment."
            if is_retryable(e)
            else "Something went wrong generating your session. Please try again."
        )
        yield {"event": "error", "data": json.dumps({"kind": "empty", "message": user_msg})}
```

Also remove the now-unused imports from `sessions.py`:
- Remove `run_research` import (no longer called directly in router)
- Remove `_generate_title`, `_parse_json_safe` import from `session_workflow` (title is now a step)

**Step 2: Run existing session storage tests**

```bash
python -m pytest tests/test_session_storage.py -v
```
Expected: all PASS (these test SQLite round-trips, not the router).

**Step 3: Commit**

```bash
git add backend/app/routers/sessions.py
git commit -m "feat: update sessions router to use full workflow pipeline, remove inline research and title logic"
```

---

## Task 10: Update chat router to load notes from SQLite

**Files:**
- Modify: `backend/app/routers/chat.py`

**Step 1: Write failing test**

Create `backend/tests/test_chat_router.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_chat_stream_returns_404_when_session_not_found():
    with patch("app.routers.chat._get_session_db"):
        with patch("app.routers.chat.build_session_workflow") as mock_wf_factory:
            mock_wf = MagicMock()
            mock_wf.get_session.return_value = None  # session not found
            mock_wf_factory.return_value = mock_wf

            from app.main import app
            client = TestClient(app)
            resp = client.post("/chat/stream", json={
                "message": "hello",
                "tutoring_type": "micro_learning",
                "history": [],
                "session_id": "nonexistent-session-id",
            })

    assert resp.status_code == 404


def test_chat_stream_request_no_longer_accepts_notes_field():
    """notes field removed from ChatStreamRequest — extra fields should be ignored or rejected."""
    from app.models.chat import ChatStreamRequest
    # session_id is now required
    with pytest.raises(Exception):
        ChatStreamRequest(
            message="hello",
            tutoring_type="micro_learning",
            history=[],
            # missing session_id
        )
```

**Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/test_chat_router.py -v
```
Expected: FAIL — chat router doesn't check SQLite yet.

**Step 3: Rewrite `chat.py` router**

```python
import json
import logging
from typing import AsyncGenerator

import asyncio
from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatStreamRequest
from app.agents.chat_agent import build_chat_agent, build_chat_messages
from app.config import get_settings
from app.workflows.session_workflow import build_session_workflow, _get_session_db
from agno.db.sqlite import SqliteDb

logger = logging.getLogger("super_tutor.chat")
router = APIRouter()


def _get_traces_db() -> SqliteDb:
    if not hasattr(_get_traces_db, "_instance"):
        settings = get_settings()
        _get_traces_db._instance = SqliteDb(
            db_file=settings.trace_db_path,
            id="super_tutor_traces",
        )
    return _get_traces_db._instance


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest):
    """
    SSE token stream for a single chat turn.
    Loads notes from SQLite session state — notes are no longer sent in the request body.
    Returns 404 if the session_id is not found in SQLite.
    """
    # Load notes from SQLite session state
    wf = build_session_workflow(
        session_id=request.session_id,
        session_db=_get_session_db(),
    )
    session = await asyncio.to_thread(wf.get_session, session_id=request.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{request.session_id}' not found. Please create a new session.",
        )
    notes = session.session_state.get("notes", "")

    agent = build_chat_agent(request.tutoring_type, notes, db=_get_traces_db())
    messages = build_chat_messages(
        [m.model_dump() for m in request.history],
        request.message,
    )

    logger.info(
        "Chat stream — session_id=%s tutoring_type=%s history_turns=%d",
        request.session_id,
        request.tutoring_type,
        len(request.history),
    )

    async def event_generator() -> AsyncGenerator[dict, None]:
        try:
            async for chunk in agent.arun(messages, stream=True, session_id=request.session_id):
                if chunk.event == "RunContent" and chunk.content:
                    yield {
                        "event": "token",
                        "data": json.dumps({"token": chunk.content}),
                    }
            try:
                await agent.aset_session_name(
                    session_id=request.session_id,
                    session_name=request.message,
                )
            except Exception as e:
                logger.warning("Could not set session name: %s", e)
            yield {"event": "done", "data": json.dumps({})}
        except Exception as e:
            logger.error("Chat stream error: %s", e, exc_info=True)
            from app.utils.retry import is_retryable
            user_message = (
                "The AI is temporarily busy — please try again in a moment."
                if is_retryable(e)
                else "Something went wrong. Please try again."
            )
            yield {"event": "error", "data": json.dumps({"error": user_message})}

    return EventSourceResponse(event_generator())
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_chat_router.py tests/test_models.py -v
```
Expected: all PASS.

**Step 5: Run full backend test suite**

```bash
python -m pytest tests/ -v
```
Expected: all PASS.

**Step 6: Commit**

```bash
git add backend/app/routers/chat.py backend/tests/test_chat_router.py
git commit -m "feat: chat router loads notes from SQLite session state, removes notes from request body"
```

---

## Task 11: Update frontend TypeScript types

**Files:**
- Modify: `frontend/src/types/session.ts`

**Step 1: Update `session.ts`**

```typescript
export type TutoringType = "micro_learning" | "teaching_a_kid" | "advanced";
export type SessionType = "url" | "topic" | "paste";

export interface SessionRequest {
  url?: string;
  paste_text?: string;
  topic_description?: string;
  tutoring_type: TutoringType;
  focus_prompt?: string;
  generate_flashcards?: boolean;
  generate_quiz?: boolean;
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface QuizQuestion {
  question: string;
  options: string[]; // exactly 4
  answer_index: number; // 0-3
}

export interface SessionResult {
  session_id: string;
  source_title: string;
  tutoring_type: TutoringType;
  session_type: SessionType;
  sources?: string[];
  notes: string; // markdown
  flashcards: Flashcard[];
  quiz: QuizQuestion[];
  errors?: Record<string, string>;
  chat_intro: string;
}

export interface ProgressEvent { message: string; }
export type CompleteEvent = SessionResult;
export interface ErrorEvent { kind: "paywall" | "invalid_url" | "empty" | "unreachable"; }
export interface WarningEvent { message: string; }

export const SSE_STEPS = ["Reading the article...", "Crafting your notes...", "Finishing up..."] as const;
export const TOPIC_SSE_STEPS = ["Researching your topic...", "Crafting your notes...", "Finishing up..."] as const;
export const SSE_STEPS_WITH_FLASHCARDS = [...SSE_STEPS.slice(0, -1), "Generating flashcards...", "Finishing up..."] as const;
export const SSE_STEPS_WITH_QUIZ = [...SSE_STEPS.slice(0, -1), "Generating quiz...", "Finishing up..."] as const;
export const SSE_STEPS_FULL = ["Reading the article...", "Crafting your notes...", "Generating flashcards...", "Generating quiz...", "Finishing up..."] as const;
export const TOPIC_SSE_STEPS_FULL = ["Researching your topic...", "Crafting your notes...", "Generating flashcards...", "Generating quiz...", "Finishing up..."] as const;
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/types/session.ts
git commit -m "feat: add generate_flashcards/quiz to SessionRequest, chat_intro to SessionResult, expand SSE_STEPS"
```

---

## Task 12: Update create page — add opt-in checkboxes

**Files:**
- Modify: `frontend/src/app/create/page.tsx`

**Step 1: Add state and checkboxes to `CreateForm`**

Add two new state variables after the existing state declarations:

```typescript
const [generateFlashcards, setGenerateFlashcards] = useState(false);
const [generateQuiz, setGenerateQuiz] = useState(false);
```

Update the `payload` object in `handleSubmit`:

```typescript
const payload: SessionRequest = {
  tutoring_type: selectedMode,
  focus_prompt: focusPrompt || undefined,
  generate_flashcards: generateFlashcards,
  generate_quiz: generateQuiz,
  ...(inputMode === "topic"
    ? { topic_description: topicDescription }
    : pasteText
    ? { paste_text: pasteText }
    : { url }),
};
```

Add the checkboxes below the focus prompt field and above the submit button:

```tsx
{/* Upfront generation options */}
<fieldset className="border-none p-0 m-0">
  <legend className="text-sm font-medium text-zinc-500 mb-3">
    Generate during session creation{" "}
    <span className="text-zinc-400 font-normal">(optional — can also generate later)</span>
  </legend>
  <div className="flex flex-col gap-2">
    {[
      { id: "generate_flashcards", label: "Flashcards", checked: generateFlashcards, onChange: setGenerateFlashcards },
      { id: "generate_quiz", label: "Quiz", checked: generateQuiz, onChange: setGenerateQuiz },
    ].map(({ id, label, checked, onChange }) => (
      <label key={id} className="flex items-center gap-3 cursor-pointer">
        <input
          type="checkbox"
          id={id}
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="w-4 h-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
        />
        <span className="text-sm text-zinc-700">{label}</span>
      </label>
    ))}
  </div>
</fieldset>
```

**Step 2: Verify the page compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/app/create/page.tsx
git commit -m "feat: add generate flashcards/quiz opt-in checkboxes to create page"
```

---

## Task 13: Update loading page — dynamic SSE steps

**Files:**
- Modify: `frontend/src/app/loading/page.tsx`

**Step 1: Update `LoadingContent` to pick steps dynamically**

Add `generateFlashcards` and `generateQuiz` from search params, then pick the correct steps array:

```typescript
const generateFlashcards = searchParams.get("generate_flashcards") === "true";
const generateQuiz = searchParams.get("generate_quiz") === "true";
const isTopic = inputMode === "topic";

const steps = (() => {
  if (isTopic && generateFlashcards && generateQuiz) return TOPIC_SSE_STEPS_FULL;
  if (!isTopic && generateFlashcards && generateQuiz) return SSE_STEPS_FULL;
  if (generateFlashcards) return isTopic ? [...TOPIC_SSE_STEPS.slice(0,-1), "Generating flashcards...", "Finishing up..."] : SSE_STEPS_WITH_FLASHCARDS;
  if (generateQuiz) return isTopic ? [...TOPIC_SSE_STEPS.slice(0,-1), "Generating quiz...", "Finishing up..."] : SSE_STEPS_WITH_QUIZ;
  return isTopic ? TOPIC_SSE_STEPS : SSE_STEPS;
})();
```

Also update the router `push` in `create/page.tsx` to include the flags in the query string:

```typescript
router.push(
  `/loading?session_id=${session_id}&tutoring_type=${selectedMode}&focus_prompt=${encodeURIComponent(focusPrompt)}&input_mode=${inputMode}&generate_flashcards=${generateFlashcards}&generate_quiz=${generateQuiz}`
);
```

**Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 3: Commit**

```bash
git add frontend/src/app/loading/page.tsx frontend/src/app/create/page.tsx
git commit -m "feat: dynamic SSE progress steps based on generate_flashcards/quiz flags"
```

---

## Task 14: Update study page — chat_intro + remove notes from chat request

**Files:**
- Modify: `frontend/src/app/study/[sessionId]/page.tsx`

**Step 1: Show `chat_intro` as first chat message**

Replace the `chatHistory` initial state with:

```typescript
const [chatHistory, setChatHistory] = useState<{ role: "user" | "assistant"; content: string }[]>(() => {
  try {
    const stored = localStorage.getItem(`chat:${sessionId}`);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
});
```

This stays the same. The intro is rendered separately — add it above the message list in the chat panel:

```tsx
{/* Chat intro — shown only when history is empty */}
{chatHistory.length === 0 && session.chat_intro && (
  <div className="flex justify-start">
    <div className="max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed bg-zinc-100 text-zinc-900 rounded-bl-sm">
      {session.chat_intro}
    </div>
  </div>
)}
```

Remove the existing empty-state paragraph:
```tsx
// Remove this:
{chatHistory.length === 0 && (
  <p className="text-xs text-zinc-400 text-center mt-8">
    Ask anything about the session content.
  </p>
)}
```

**Step 2: Remove `notes` from the chat fetch body in `sendMessage`**

```typescript
body: JSON.stringify({
  message: userMessage,
  tutoring_type: session.tutoring_type,
  // Send last 6 prior turns (client-side cap; backend is stateless)
  history: history.slice(0, -1).slice(-6),
  session_id: sessionId,
}),
```

(`notes` field removed — backend now loads from SQLite.)

**Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 4: Run the dev server and manually verify**

```bash
cd frontend && npm run dev
```

Check:
1. Create page shows flashcard/quiz checkboxes
2. Loading page shows the right number of steps
3. Study page shows chat_intro bubble when chat opens
4. Chat works without sending notes in request body
5. Regenerate still works (on-demand path unchanged)

**Step 5: Commit**

```bash
git add frontend/src/app/study/[sessionId]/page.tsx
git commit -m "feat: show chat_intro as first chat bubble, remove notes from chat request body"
```

---

## Task 15: Final verification and cleanup

**Step 1: Run full backend test suite**

```bash
cd backend && python -m pytest tests/ -v
```
Expected: all PASS.

**Step 2: Run TypeScript check**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

**Step 3: Check for leftover unused imports in sessions.py**

Verify these are removed (no longer needed directly in the router):
- `run_research` from `app.agents.research_agent`
- `_generate_title`, `_parse_json_safe` from `app.workflows.session_workflow` (they're still used internally by the workflow but not by the router)

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: cleanup unused imports after workflow refactor"
```
