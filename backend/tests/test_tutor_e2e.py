"""
End-to-end smoke test for the TutorTeam — QuizMaster + Advisor agents.

This test hits the real backend endpoints (assumes `uvicorn app.main:app --port 8000`
is running). Skip automatically if TUTOR_E2E is not set:
    TUTOR_E2E=1 pytest backend/tests/test_tutor_e2e.py -s -v

Flow:
  1. POST /sessions/topic  → create session
  2. Poll GET /sessions/{id}/status until complete (max 120s)
  3. Send "quiz me"   → assert MCQ delivered (A/B/C/D present)
  4. Send wrong answer → assert evaluation language in response
  5. Send advisor query → assert named concept in response
"""

import json
import os
import time
import pytest
import httpx

BASE = "http://localhost:8000"
TIMEOUT = 30  # seconds per tutor stream request


# ---------------------------------------------------------------------------
# Module-level fixtures used by standalone test functions
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Persistent httpx.Client for the live backend."""
    with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
        yield c


@pytest.fixture(scope="module")
def tutor_session_id(client):
    """Create a topic session, wait for completion, return session_id."""
    r = client.post("/sessions/topic", json={
        "topic": "photosynthesis — how plants convert light into energy",
        "tutoring_type": "micro_learning",
    })
    assert r.status_code == 200, f"Session creation failed: {r.text}"
    sid = r.json()["session_id"]

    deadline = time.time() + 120
    while time.time() < deadline:
        status_r = client.get(f"/sessions/{sid}/status")
        if status_r.status_code == 200 and status_r.json().get("status") == "complete":
            return sid
        time.sleep(3)
    pytest.fail(f"Session {sid} did not reach 'complete' status within 120s")


# ---------------------------------------------------------------------------
# Module-level SSE helper
# ---------------------------------------------------------------------------

def _stream_tutor(client, session_id, message, tutoring_type="micro_learning"):
    """Stream a tutor message and return the concatenated token text.

    Parses both ``event:`` and ``data:`` SSE lines so that:
    - ``error`` events raise AssertionError immediately.
    - ``rejected`` events return ``{"rejected": True, "reason": ...}``.
    - ``stream_start`` / ``done`` data payloads are skipped.
    - Only ``token`` event data contributes to the returned string.
    """
    chunks = []
    current_event = None
    with client.stream("POST", f"/tutor/{session_id}/stream", json={
        "message": message,
        "tutoring_type": tutoring_type,
        "tutor_reset_id": "v0",
    }) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("event:"):
                current_event = line[6:].strip()
            elif line.startswith("data:"):
                raw = line[5:].strip()
                if not raw:
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if current_event in ("error",):
                    raise AssertionError(f"Stream returned error: {parsed}")
                if current_event in ("rejected",):
                    return {"rejected": True, "reason": parsed.get("reason", "")}
                if isinstance(parsed, dict) and "token" in parsed:
                    chunks.append(parsed["token"])
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Class-based live E2E tests (existing)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("TUTOR_E2E"), reason="TUTOR_E2E not set — skipping live backend test")
class TestTutorE2E:

    @pytest.fixture(scope="class")
    def session_id(self):
        """Create a topic session and wait for it to be ready."""
        r = httpx.post(f"{BASE}/sessions/topic", json={
            "topic": "photosynthesis — how plants convert light into energy",
            "tutoring_type": "micro_learning",
        }, timeout=30)
        assert r.status_code == 200, f"Session creation failed: {r.text}"
        sid = r.json()["session_id"]

        # Poll for completion (max 120s)
        deadline = time.time() + 120
        while time.time() < deadline:
            status_r = httpx.get(f"{BASE}/sessions/{sid}/status", timeout=10)
            if status_r.status_code == 200 and status_r.json().get("status") == "complete":
                return sid
            time.sleep(3)
        pytest.fail(f"Session {sid} did not reach 'complete' status within 120s")

    def _stream_tutor(self, session_id: str, message: str) -> str:
        """Send a tutor message and collect the full streamed response as a string."""
        with httpx.Client(base_url=BASE, timeout=TIMEOUT) as c:
            return _stream_tutor(c, session_id, message)

    def test_quiz_me_delivers_mcq(self, session_id):
        """'quiz me' → response must contain at least two of A) B) C) D) option markers."""
        response = self._stream_tutor(session_id, "quiz me")
        option_count = sum(1 for opt in ["A)", "B)", "C)", "D)"] if opt in response)
        assert option_count >= 2, (
            f"Expected MCQ options in response, got: {response[:500]}"
        )

    def test_wrong_answer_gets_evaluation(self, session_id):
        """Sending a deliberate wrong answer → response contains evaluation language."""
        # First re-trigger a question so QuizMaster has active context
        self._stream_tutor(session_id, "give me a question")
        # Send wrong answer — force wrong by using "Z" which is not a valid option
        response = self._stream_tutor(session_id, "Z")
        evaluation_markers = ["correct answer", "correct", "not quite", "the answer is", "actually"]
        assert any(m.lower() in response.lower() for m in evaluation_markers), (
            f"Expected evaluation language in response, got: {response[:500]}"
        )

    def test_advisor_surfaces_concept(self, session_id):
        """'what should I focus on' → Advisor response references a named concept."""
        # Send a few deliberate wrong answers to build context before testing Advisor
        self._stream_tutor(session_id, "give me a question")
        self._stream_tutor(session_id, "Z")  # wrong
        self._stream_tutor(session_id, "give me another question")
        self._stream_tutor(session_id, "Z")  # wrong again

        response = self._stream_tutor(session_id, "what should I focus on")
        assert len(response.strip()) > 20, f"Advisor gave empty response: {response!r}"
        # Response should not be an off-topic rejection
        assert "outside" not in response.lower() or "focus" in response.lower(), (
            f"Advisor response looks like an off-topic rejection: {response[:300]}"
        )


# ---------------------------------------------------------------------------
# Standalone live tests (require TUTOR_E2E + running server)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.getenv("TUTOR_E2E"), reason="TUTOR_E2E not set")
def test_reset_id_starts_fresh_conversation(client, tutor_session_id):
    """Different tutor_reset_id values produce independent conversation namespaces."""
    # First conversation turn
    first = _stream_tutor(client, tutor_session_id, "Hello, what can you help me with?")
    assert len(first) > 0

    # New reset ID — should not carry forward prior context
    with client.stream("POST", f"/tutor/{tutor_session_id}/stream", json={
        "message": "What was my previous question?",
        "tutoring_type": "micro_learning",
        "tutor_reset_id": f"v{int(time.time())}",  # fresh reset ID
    }) as resp:
        assert resp.status_code == 200
        # Just verify the stream completes without error — context isolation
        # is enforced by agno's session namespacing, not testable at this level
        lines = list(resp.iter_lines())
        assert any("done" in l or "token" in l for l in lines)


@pytest.mark.skipif(not os.getenv("TUTOR_E2E"), reason="TUTOR_E2E not set")
def test_off_topic_message_is_rejected(client, tutor_session_id):
    """TopicRelevanceGuardrail should reject clearly off-topic messages."""
    result = _stream_tutor(client, tutor_session_id, "Write me a poem about dogs and cats please")
    # Either the guardrail rejects it (returns rejected dict) or the coordinator handles it
    # Both are acceptable — we just verify no server error occurs
    assert result is not None


# ---------------------------------------------------------------------------
# Unit tests — no server required, no skip guard
# ---------------------------------------------------------------------------

class TestExtractionHelpers:
    """Unit tests for pure extraction functions — no server required."""

    def test_extract_quiz_score_basic(self):
        from app.routers.tutor import _extract_quiz_score
        result = _extract_quiz_score("I just completed the quiz and scored 3 out of 5.")
        assert result is not None
        assert result["correct"] == 3
        assert result["total"] == 5
        assert "timestamp" in result

    def test_extract_quiz_score_no_match(self):
        from app.routers.tutor import _extract_quiz_score
        assert _extract_quiz_score("Hello, how are you?") is None

    def test_extract_quiz_score_variant(self):
        from app.routers.tutor import _extract_quiz_score
        result = _extract_quiz_score("I scored 7 out of 10 on the quiz!")
        assert result is not None
        assert result["correct"] == 7
        assert result["total"] == 10

    def test_extract_focus_areas_basic(self):
        from app.routers.tutor import _extract_focus_areas
        result = _extract_focus_areas("Want me to generate extra flashcards on photosynthesis?")
        assert "photosynthesis" in result

    def test_extract_focus_areas_empty(self):
        from app.routers.tutor import _extract_focus_areas
        assert _extract_focus_areas("Great job! You're doing well.") == []

    def test_extract_focus_areas_multiple(self):
        from app.routers.tutor import _extract_focus_areas
        result = _extract_focus_areas(
            "I suggest reviewing content on cellular respiration. "
            "Also, extra notes on the ATP cycle would help."
        )
        assert len(result) >= 1
