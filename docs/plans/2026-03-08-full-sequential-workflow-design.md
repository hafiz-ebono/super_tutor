# Design: Full Sequential Workflow with Opt-in Generation

**Date:** 2026-03-08
**Status:** Approved

---

## Problem

The current workflow only runs the NotesAgent. Flashcards and quiz are generated on-demand via separate HTTP requests from the study page, after session creation. There is no opt-in path to generate all study materials upfront. Source content is not persisted in session state. The chat agent receives notes via the request body rather than loading from SQLite.

---

## Solution

Extend the Agno Workflow to a full sequential pipeline. Add opt-in flags on the session creation request so users can choose to generate flashcards and quiz during session creation. Persist source content in session state. Clean up the chat API to load notes from SQLite instead of accepting them in the request body. Add a persona-adapted chat intro message.

---

## Pipeline

```
Topic path:
  research_step → notes_step → [flashcards_step] → [quiz_step] → title_step

URL / Paste path:
  (extraction runs before workflow in the router, as now)
  notes_step → [flashcards_step] → [quiz_step] → title_step

[] = conditional — only included when opted in via request flags
```

The workflow step list is built dynamically per request based on `session_type` and the opt-in flags.

---

## Session State Schema

All fields are persisted to SQLite automatically by Agno's `save_session()` after each step.

```python
session_state = {
    "source_content": str,       # raw text: researched / extracted / pasted
    "sources": list[str],        # URLs from ResearchAgent (topic path only)
    "notes": str,                # markdown from NotesAgent
    "flashcards": list[dict],    # [{front, back}] — empty list if not opted in
    "quiz": list[dict],          # [{question, options, answer_index}] — empty list if not opted in
    "title": str,                # AI-generated 3-5 word title
    "tutoring_type": str,
    "session_type": str,         # "url" | "topic" | "paste"
    "errors": dict,              # {"flashcards": "...", "quiz": "..."} non-fatal step errors
    "chat_intro": str,           # persona-adapted welcome message for chat panel
}
```

---

## Step Error Strategy

| Step | Input | Failure Mode |
|------|-------|-------------|
| `research_step` | topic_description | **Fatal** — aborts workflow, SSE error event |
| `notes_step` | source_content | **Fatal** — aborts workflow, SSE error event |
| `flashcards_step` | source_content | **Non-fatal** — writes to `errors["flashcards"]`, session continues |
| `quiz_step` | source_content | **Non-fatal** — writes to `errors["quiz"]`, session continues |
| `title_step` | source_content | **Non-fatal** — falls back to `_extract_title(notes)` |

Each step handles:
- Provider/network errors → retried via `run_with_retry` (up to `AGENT_MAX_RETRIES`)
- `InputCheckError` → caught, re-raised as `RuntimeError` with user-friendly message
- `OutputCheckError` → caught, treated as empty output
- Empty/short output → validated post-run, raises `RuntimeError`
- JSON parse failure (flashcards/quiz) → returns empty list, writes to errors dict

---

## API Changes

### `SessionRequest` — two new fields

```python
generate_flashcards: bool = False
generate_quiz: bool = False
```

### `SessionResult` — one new field

```python
chat_intro: str  # persona-adapted greeting shown as first chat bubble
```

### `POST /chat/stream` — request body simplified

Remove `notes` from the request body. The chat router loads notes from `session_state` via SQLite using `session_id`. This makes the chat API stateless from the client's perspective while being server-authoritative about what the agent is grounded in.

Before:
```json
{"message": "...", "notes": "...", "tutoring_type": "...", "history": [...], "session_id": "..."}
```

After:
```json
{"message": "...", "tutoring_type": "...", "history": [...], "session_id": "..."}
```

---

## Chat Agent Changes

- Grounded in **notes** (not raw source content) — structured, condensed, persona-consistent
- Source content stored in `session_state["source_content"]` for traceability and future use
- Notes loaded from SQLite at request time via `session_id`
- `chat_intro` is a static template string (no extra LLM call) keyed on `tutoring_type`:

| Persona | Intro message |
|---------|--------------|
| `micro_learning` | `"Session assistant here. Ask me anything — I'll keep it short."` |
| `teaching_a_kid` | `"Hi! I'm your study buddy for this session! What would you like to understand?"` |
| `advanced` | `"I'm your session tutor. I have full context of this material — ask me anything, including edge cases and nuance."` |

---

## Frontend Changes

| File | Change |
|------|--------|
| `src/types/session.ts` | Add `generate_flashcards?: boolean`, `generate_quiz?: boolean` to `SessionRequest`; add `chat_intro: string` to `SessionResult` |
| `src/app/create/page.tsx` | Add two opt-in checkboxes below the tutoring mode selector |
| `src/app/loading/page.tsx` | Extend SSE_STEPS / TOPIC_SSE_STEPS to include flashcard, quiz, and title steps when opted in |
| `src/app/study/[sessionId]/page.tsx` | Show `session.chat_intro` as first bubble in chat panel; remove `notes` from chat request body |

---

## What Does Not Change

- Content extraction (trafilatura) still runs before the workflow in the router
- On-demand regeneration endpoints (`POST /sessions/{id}/regenerate/{section}`) still exist for when the user did not opt in during creation
- Guardrails (pre + post hooks) applied to all agents unchanged
- AgentOS tracing via `db=` injection unchanged
- `session_id` threading unchanged
