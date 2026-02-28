---
phase: 04-chat-backend
plan: 01
subsystem: api
tags: [agno, pydantic, chat, streaming, agents]

# Dependency graph
requires:
  - phase: 04-chat-backend
    provides: PERSONAS dict with micro_learning, teaching_a_kid, advanced keys
  - phase: 04-chat-backend
    provides: model_factory.get_model() for agent construction
provides:
  - ChatMessage and ChatStreamRequest Pydantic models (backend/app/models/chat.py)
  - build_chat_agent() stateless chat agent builder with grounding (backend/app/agents/chat_agent.py)
  - build_chat_messages() history + message to List[Message] converter
affects:
  - 04-chat-backend/04-02 (chat streaming router will import ChatStreamRequest, build_chat_agent, build_chat_messages)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Stateless agent per request — new Agent constructed on every request, no server-side session state
    - Hard grounding instruction pattern — "ONLY from the session material" + explicit fallback string
    - List[Message] input to agent.arun() — history + current turn as typed Message objects

key-files:
  created:
    - backend/app/models/chat.py
    - backend/app/agents/chat_agent.py
  modified: []

key-decisions:
  - "Stateless agent per request: new Agent on each call, client owns history state"
  - "Hard grounding wording: 'Answer ONLY from the session material' with explicit fallback response string, not soft language"
  - "List[Message] approach: build_chat_messages appends history + current message; last Message(role=user) IS the current turn per Agno 2.5.2 behavior"
  - "No server-side history cap: backend accepts whatever client sends; 6-turn cap is client-side responsibility"

patterns-established:
  - "Grounding pattern: embed notes between --- SESSION MATERIAL --- / --- END MATERIAL --- markers"
  - "Agent builder pattern: same structure as notes_agent.py (PERSONAS lookup + get_model() + f-string instructions)"

requirements-completed: [CHAT-04, CHAT-05, CHAT-06, CHAT-07]

# Metrics
duration: 2min
completed: 2026-02-28
---

# Phase 4 Plan 01: Chat Models and Agent Builder Summary

**ChatMessage/ChatStreamRequest Pydantic models + stateless Agno chat agent builder with hard notes-grounding and List[Message] message conversion**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-28T14:41:59Z
- **Completed:** 2026-02-28T14:43:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- ChatMessage model with role Literal["user","assistant"] and content field
- ChatStreamRequest model with message, notes, tutoring_type, history (default []) and str_strip_whitespace
- build_chat_agent() builds stateless per-request Agno Agent with PERSONAS tone + hard grounding instruction ("Answer ONLY from the session material")
- build_chat_messages() converts frontend history list plus current message into List[Message] for agent.arun()

## Task Commits

Each task was committed atomically:

1. **Task 1: Create ChatMessage and ChatStreamRequest Pydantic models** - `1a00003` (feat)
2. **Task 2: Create chat_agent.py with agent builder and message converter** - `30f1312` (feat)

## Files Created/Modified

- `backend/app/models/chat.py` - ChatMessage and ChatStreamRequest Pydantic models; tutoring_type literals match session.py for direct router passthrough
- `backend/app/agents/chat_agent.py` - build_chat_agent (stateless Agent per request, grounded in notes) and build_chat_messages (history + current message to List[Message])

## Agent Instruction Structure

`build_chat_agent` instructions follow this layout:

```
{persona}  ← from PERSONAS[tutoring_type]

You are a tutoring assistant helping a student understand the session material below.
Answer ONLY from the session material. If the student's question is not covered in the
material, respond: "I can only answer about this session's material."
Do not use outside knowledge under any circumstances.

# TODO: truncate notes if > 3000 tokens (current notes are compressed, safe for MVP)

--- SESSION MATERIAL ---
{notes}
--- END MATERIAL ---
```

Grounding wording: "Answer ONLY from the session material" (hard, not soft) with an explicit fallback response string, per RESEARCH.md Pitfall 3.

## build_chat_messages Contract (Agno 2.5.2)

`build_chat_messages(history, message)` returns `List[Message]` where:
- Each history turn becomes a `Message(role=..., content=...)` in order
- The current user message is appended as `Message(role="user", content=message)` at the end
- Total length is `len(history) + 1`
- Last element always has `role="user"`

Per Agno 2.5.2 `get_run_messages()` behavior: when input is `List[Message]`, Agno appends them after the system prompt without creating an additional user message. The final `Message(role="user")` IS the current user turn.

## Decisions Made

- Stateless agent per request — no server-side session state; client owns conversation history
- Hard grounding language: "ONLY from the session material" + explicit fallback string (not soft "try to focus on")
- No server-side history cap: backend accepts whatever the client sends; 6-turn limit is enforced client-side (STATE.md decision)
- `str_strip_whitespace = True` on ChatStreamRequest matches project convention from session.py

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The system Python did not have agno installed; used `.venv/bin/python` from `backend/.venv/` for verification. This is normal project setup — the venv is where backend dependencies live.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `backend/app/models/chat.py` ready to import in chat router (`from app.models.chat import ChatStreamRequest`)
- `backend/app/agents/chat_agent.py` ready to import in chat router (`from app.agents.chat_agent import build_chat_agent, build_chat_messages`)
- Plan 02 (chat streaming router) can proceed immediately

---
*Phase: 04-chat-backend*
*Completed: 2026-02-28*
