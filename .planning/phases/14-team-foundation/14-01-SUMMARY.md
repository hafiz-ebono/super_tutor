---
phase: 14-team-foundation
plan: 01
subsystem: api
tags: [agno, team, coordinator, explainer, pydantic, sqlite, sse]

# Dependency graph
requires:
  - phase: 12-backend-upload-endpoint
    provides: session storage with source_content and notes in SQLite traces_db
  - phase: 04-chat-backend
    provides: guardrails, model_factory, and chat agent patterns reused by Explainer

provides:
  - build_tutor_team() factory — Agno Team in coordinate mode with coordinator + Explainer member
  - TUTOR_TOKEN_EVENTS and TUTOR_ERROR_EVENT constants for router SSE filtering
  - TutorStreamRequest Pydantic model with message, tutoring_type, session_id validation
  - tutor_history_window and rate_limit_tutor config settings

affects:
  - 14-02-tutor-router (imports build_tutor_team, TUTOR_TOKEN_EVENTS, TutorStreamRequest directly)
  - 15-guardrails (Explainer's pre_hooks pattern established here)
  - 16-tutor-frontend (TutorStreamRequest defines the request contract)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Per-request Agno Team factory (never reuse Team instance across requests)
    - Grounding block pattern: inject source_content + notes into both coordinator and specialist system prompts
    - History at Team level only — specialist agents have no db= (avoids duplicate session rows)
    - Namespace isolation: tutor:{session_id} prefix prevents collision with workflow session rows

key-files:
  created:
    - backend/app/agents/tutor_team.py
    - backend/app/models/tutor.py
  modified:
    - backend/app/config.py

key-decisions:
  - "TeamMode.coordinate chosen over route: coordinate mode gives coordinator framing tokens before Explainer content; route mode suppresses coordinator output (respond_directly=True), which would violate the brief-acknowledgment-prefix requirement"
  - "History managed at Team level only — Explainer has no db= to avoid duplicate session rows (RESEARCH.md Pitfall 4)"
  - "PROMPT_INJECTION_GUARDRAIL applied to Explainer only, not the coordinator — coordinator does routing/rejection via system prompt, not pre-hook"
  - "tutor_history_window default 10 (vs chat 20): tutor conversations tend to be deeper per-turn but shorter in total turn count; 10 is a sensible conservative default adjustable via env var"
  - "Grounding block includes both source_content and notes when notes non-empty: notes are AI-generated summary derivatives that complement the authoritative source_content"

patterns-established:
  - "Grounding block pattern: _build_grounding_block(source_content, notes) wraps material in --- SESSION MATERIAL --- headers, appends notes with --- SESSION NOTES (summary) --- when non-empty"
  - "Team factory pattern: fresh Team per request with db= shared from DI, session_id passed at call time (not at construction)"
  - "TUTOR_TOKEN_EVENTS set pattern: router imports this constant to filter {TeamRunContent, TeamRunIntermediateContent} without duplicating enum logic"

requirements-completed: [TEAM-01, TEAM-02, TEAM-03, CONTENT-01, GUARD-03]

# Metrics
duration: 2min
completed: 2026-03-15
---

# Phase 14 Plan 01: Team Foundation — Factory and Models Summary

**Agno Team factory with coordinator + Explainer in coordinate mode, grounding block construction, TutorStreamRequest model, and tutor config settings for the Personal Tutor backend**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-14T22:00:56Z
- **Completed:** 2026-03-14T22:02:25Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `build_tutor_team()` factory builds a fresh Agno Team on every request with TeamMode.coordinate, one Explainer member with PROMPT_INJECTION_GUARDRAIL, and SQLite persistence wired via shared traces_db
- `TUTOR_TOKEN_EVENTS` exports the two event strings the router must filter (`TeamRunContent`, `TeamRunIntermediateContent`) so coordinator acknowledgment prefix and Explainer tokens both stream through
- `TutorStreamRequest` validates message (1-5000 chars), tutoring_type enum, and session_id — mirrors existing ChatStreamRequest style
- `tutor_history_window: int = 10` and `rate_limit_tutor: str = "60/minute"` added to Settings for env-var-configurable tuning

## Task Commits

Each task was committed atomically:

1. **Task 1: Build tutor_team.py** - `a519b10` (feat)
2. **Task 2: Add TutorStreamRequest model and tutor_history_window config** - `1eb3df0` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/app/agents/tutor_team.py` — build_tutor_team() factory, _build_grounding_block(), TUTOR_TOKEN_EVENTS, TUTOR_ERROR_EVENT
- `backend/app/models/tutor.py` — TutorStreamRequest Pydantic model
- `backend/app/config.py` — tutor_history_window and rate_limit_tutor settings added to Settings class

## Decisions Made
- **TeamMode.coordinate**: Chosen over `route` because coordinate mode allows the coordinator to emit framing tokens (brief acknowledgment prefix) before the Explainer's content streams through. Route mode sets `respond_directly=True` — coordinator output is suppressed and Explainer content passes verbatim, which contradicts the spec requirement for a one-sentence acknowledgment prefix.
- **History at Team level only**: Explainer agent has no `db=` or `add_history_to_context=True`. Confirmed from RESEARCH.md Pitfall 4 — giving the Explainer its own DB creates duplicate/conflicting session rows.
- **Guardrail placement**: `PROMPT_INJECTION_GUARDRAIL` applied to Explainer only. Coordinator does rejection via system prompt instructions, not pre-hook — coordinator needs to see the full message to make routing decisions.
- **tutor_history_window=10**: Balances context quality vs. unbounded growth. Tutor conversations are deeper per-turn but total turn counts tend to be lower than open-ended chat. Default is env-var overridable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Task 2 (config) completed before Task 1 verification could fully pass**
- **Found during:** Task 1 verification
- **Issue:** `build_tutor_team()` calls `get_settings().tutor_history_window` which didn't exist yet — Task 1 verification raised `AttributeError` on first run
- **Fix:** Executed Task 2 (config.py + models/tutor.py) before re-running Task 1 verification. Task ordering in plan assumed sequential but the config dependency meant Task 2 must precede Task 1's final verification run. Both tasks were then committed separately in their natural order.
- **Files modified:** backend/app/config.py (Task 2 commit)
- **Verification:** All Task 1 and Task 2 verify commands passed after reordering
- **Committed in:** a519b10 (Task 1 commit), 1eb3df0 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — execution order adjusted)
**Impact on plan:** Trivial. Both tasks completed correctly and committed atomically. No scope creep.

## Issues Encountered
- Task 1 verification failed on first run because `tutor_history_window` config field did not exist yet. Resolved by executing Task 2 first, then re-running Task 1 verification. Expected — the plan's tasks have a forward config dependency.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- `build_tutor_team()` is ready for import by the tutor router (Plan 02)
- `TutorStreamRequest` is the request body model for `POST /tutor/{session_id}/stream`
- `TUTOR_TOKEN_EVENTS` and `TUTOR_ERROR_EVENT` are exported for SSE filtering in the router
- `tutor_history_window` and `rate_limit_tutor` are available in settings for the router

---
*Phase: 14-team-foundation*
*Completed: 2026-03-15*
