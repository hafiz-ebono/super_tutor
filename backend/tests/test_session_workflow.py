"""
Unit tests for build_session_workflow (Task 8).

Tests verify the conditional step-list logic without running agents or touching SQLite.
"""
from unittest.mock import MagicMock, patch

import pytest


def _make_mock_db():
    return MagicMock()


def _all_step_names(steps) -> set:
    """Recursively collect step names including nested Condition/Parallel children."""
    names = set()
    for s in steps:
        names.add(s.name)
        sub = getattr(s, "steps", None) or []
        if sub:
            names |= _all_step_names(sub)
    return names


@patch("app.workflows.session_workflow.Workflow", autospec=False)
def test_build_workflow_topic_includes_research_step(MockWorkflow):
    """Topic session must include research_step as the first step."""
    from app.workflows.session_workflow import build_session_workflow
    build_session_workflow(
        session_id="s1",
        session_db=_make_mock_db(),
        session_type="topic",
        generate_flashcards=False,
        generate_quiz=False,
    )
    call_kwargs = MockWorkflow.call_args.kwargs
    step_names = [s.name for s in call_kwargs["steps"]]
    assert step_names[0] == "research", f"Expected first step to be 'research', got {step_names}"


@patch("app.workflows.session_workflow.Workflow", autospec=False)
def test_build_workflow_url_excludes_research_step(MockWorkflow):
    """URL session: research is a Condition that won't fire (evaluator returns False)."""
    from app.workflows.session_workflow import build_session_workflow, _is_topic_session
    from agno.workflow.types import StepInput
    build_session_workflow(
        session_id="s2",
        session_db=_make_mock_db(),
        session_type="url",
        generate_flashcards=False,
        generate_quiz=False,
    )
    url_input = StepInput(additional_data={"session_type": "url"})
    assert not _is_topic_session(url_input), (
        "research evaluator must return False for url sessions"
    )


def test_build_workflow_with_flashcards_flag():
    """generate_flashcards=True: _wants_flashcards evaluator returns True."""
    from app.workflows.session_workflow import _wants_flashcards
    from agno.workflow.types import StepInput
    step_input = StepInput(additional_data={"generate_flashcards": True})
    assert _wants_flashcards(step_input)


def test_build_workflow_without_flashcards_flag():
    """generate_flashcards=False: _wants_flashcards evaluator returns False."""
    from app.workflows.session_workflow import _wants_flashcards
    from agno.workflow.types import StepInput
    step_input = StepInput(additional_data={"generate_flashcards": False})
    assert not _wants_flashcards(step_input)


def test_build_workflow_with_quiz_flag():
    """generate_quiz=True: _wants_quiz evaluator returns True."""
    from app.workflows.session_workflow import _wants_quiz
    from agno.workflow.types import StepInput
    step_input = StepInput(additional_data={"generate_quiz": True})
    assert _wants_quiz(step_input)


@patch("app.workflows.session_workflow.Workflow", autospec=False)
def test_build_workflow_always_includes_notes_and_title(MockWorkflow):
    """Every workflow must include notes (in Parallel) and title (top-level) steps."""
    from app.workflows.session_workflow import build_session_workflow
    for session_type in ("url", "paste", "topic"):
        MockWorkflow.reset_mock()
        build_session_workflow(
            session_id="s6",
            session_db=_make_mock_db(),
            session_type=session_type,
            generate_flashcards=False,
            generate_quiz=False,
        )
        call_kwargs = MockWorkflow.call_args.kwargs
        all_names = _all_step_names(call_kwargs["steps"])
        assert "notes" in all_names, f"Missing notes for session_type={session_type}"
        assert "title" in all_names, f"Missing title for session_type={session_type}"


@patch("app.workflows.session_workflow.Workflow", autospec=False)
def test_build_workflow_title_is_last_step(MockWorkflow):
    """title_step must always be the last step."""
    from app.workflows.session_workflow import build_session_workflow
    build_session_workflow(
        session_id="s7",
        session_db=_make_mock_db(),
        session_type="topic",
        generate_flashcards=True,
        generate_quiz=True,
    )
    call_kwargs = MockWorkflow.call_args.kwargs
    step_names = [s.name for s in call_kwargs["steps"]]
    assert step_names[-1] == "title", f"Expected last step to be 'title', got {step_names[-1]}"


@patch("app.workflows.session_workflow.Workflow", autospec=False)
def test_build_workflow_backward_compat_minimal_call(MockWorkflow):
    """build_session_workflow with only session_id + session_db still works (used by _guard_session)."""
    from app.workflows.session_workflow import build_session_workflow
    build_session_workflow(session_id="s8", session_db=_make_mock_db())
    assert MockWorkflow.called
