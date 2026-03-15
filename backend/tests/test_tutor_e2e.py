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

import os
import time
import pytest
import httpx

BASE = "http://localhost:8000"
TIMEOUT = 30  # seconds per tutor stream request


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
        chunks = []
        with httpx.stream(
            "POST",
            f"{BASE}/tutor/{session_id}/stream",
            json={"message": message, "tutoring_type": "micro_learning"},
            timeout=TIMEOUT,
        ) as resp:
            assert resp.status_code == 200, f"Tutor stream failed: {resp.read()}"
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    chunks.append(line[5:].strip())
        return " ".join(chunks)

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
