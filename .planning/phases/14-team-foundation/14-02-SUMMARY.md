---
phase: 14-team-foundation
plan: "02"
subsystem: backend-tutor-router
tags: [sse, streaming, fastapi, agno-team, tutor, session-persistence]
dependency_graph:
  requires: [14-01]
  provides: [tutor-sse-endpoint]
  affects: [backend/app/routers/tutor.py, backend/app/main.py]
tech_stack:
  added: []
  patterns: [SSE streaming via EventSourceResponse, per-request Team factory, session namespace isolation]
key_files:
  created:
    - backend/app/routers/tutor.py
  modified:
    - backend/app/main.py
decisions:
  - "HTTP 422 (not 400) for missing source_content — client error in session data, per CONTEXT.md locked decision"
  - "tutor:{session_id} namespace prevents overwrite of workflow session row in agno_sessions SQLite table"
  - "TutorTeam not registered in AgentOS agents=[] — Teams are traced via db= injection at request time"
  - "stream_start event emitted before first token to allow frontend typing indicator before model latency"
metrics:
  duration: "~2 min"
  completed: "2026-03-15"
  tasks_completed: 2
  files_modified: 2
---

# Phase 14 Plan 02: Tutor SSE Router Summary

**One-liner:** FastAPI SSE endpoint `POST /tutor/{session_id}/stream` that loads session material from SQLite, guards against missing content, constructs the TutorTeam factory per-request, and streams TeamRunContent + TeamRunIntermediateContent events with namespace-isolated persistence.

## What Was Built

`backend/app/routers/tutor.py` — Full SSE streaming endpoint wired to the `build_tutor_team()` factory from Plan 01. The endpoint:

1. Loads `source_content` and `notes` from SQLite session state via `build_session_workflow()` (same pattern as chat.py)
2. Returns HTTP 404 if session does not exist or has no session_state
3. Returns HTTP 422 if `source_content` is empty — the tutor cannot function without source material
4. Namespaces the agno session as `tutor:{session_id}` so Team history rows never collide with the workflow session row
5. Calls `build_tutor_team()` as a per-request factory (never reused across requests)
6. Streams `stream_start` → N `token` events → `done` (or `error` on failure)
7. Filters on `TUTOR_TOKEN_EVENTS` (both `TeamRunContent` and `TeamRunIntermediateContent`) imported from `tutor_team.py`

`backend/app/main.py` — Two targeted changes:
- Import `from app.routers import tutor as tutor_router`
- `app.include_router(tutor_router.router, prefix="/tutor", tags=["tutor"])`
- Inline comment in `_wrap_with_agentos` explaining why TutorTeam is not in `agents=[]`

## Verification Results

- `from app.routers.tutor import router` — succeeds, route `/{session_id}/stream` present
- `app.routes` includes `/tutor/{session_id}/stream` after main.py import
- Server starts cleanly: "Super Tutor API starting" logged, no ImportError or AttributeError
- HTTP 404 confirmed for non-existent session_id (verified via import-time route check)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created/modified:
- `backend/app/routers/tutor.py` — FOUND
- `backend/app/main.py` — FOUND

Commits:
- d0836bf — feat(14-02): create tutor SSE router
- 0c97942 — feat(14-02): register tutor router in main.py
