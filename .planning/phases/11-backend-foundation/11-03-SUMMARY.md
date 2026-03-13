---
phase: 11-backend-foundation
plan: 03
subsystem: api
tags: [python, fastapi, sqlite, agno, source_content, regenerate]

# Dependency graph
requires:
  - phase: 11-01
    provides: cleaner.py and document_extractor.py foundation

provides:
  - regenerate_section() reads source_content from SQLite session_state instead of notes
  - 404 raised when source_content absent (no graceful fallback)
  - input_text passed as raw source_content (no 'Content:\n' framing prefix)
  - Updated router tests use source_content fixtures and reflect new behavior

affects: [12-upload-http-layer, 13-frontend-upload]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "state.get('source_content', '') as canonical SQLite read pattern in regenerate endpoint"
    - "No framing label added to source_content before agent invocation — raw text only"

key-files:
  created: []
  modified:
    - backend/app/routers/sessions.py
    - backend/tests/test_sessions_router.py

key-decisions:
  - "source_content (not notes) is the authoritative input for flashcard/quiz regeneration"
  - "No 'Content:\\n' framing prefix — input_text = source_content raw text per CONTEXT.md decision"
  - "No graceful fallback — missing source_content raises HTTP 404 immediately"

patterns-established:
  - "Regenerate endpoint pattern: load source_content from SQLite state, pass raw to agent"

requirements-completed: [SRC-03]

# Metrics
duration: 1min
completed: 2026-03-14
---

# Phase 11 Plan 03: Regenerate Endpoint Source Content Summary

**regenerate_section() updated to read source_content from SQLite session_state instead of notes, passing raw text (no framing) to flashcard and quiz agents — SRC-03 satisfied**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-14T07:44:39Z
- **Completed:** 2026-03-14T07:45:59Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `regenerate_section()` now calls `state.get("source_content", "")` instead of `state.get("notes", "")`
- `input_text = source_content` (raw) — removed `f"Content:\n{notes}"` framing prefix
- 404 with "has no source content" message raised when source_content absent
- Both regenerate router tests renamed and updated with source_content fixtures
- Full suite of 88 tests passes (excluding pre-existing pypdf dependency gap in 11-01)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update regenerate_section() to load source_content from SQLite** - `9a25ef2` (feat)
2. **Task 2: Update router tests for source_content-based regenerate** - `fd8f1be` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/app/routers/sessions.py` - regenerate_section() uses source_content from SQLite, raw input_text, updated docstring
- `backend/tests/test_sessions_router.py` - Two regenerate tests renamed and fixture updated

## Decisions Made
- No framing prefix added to source_content before passing to agent — raw text only per CONTEXT.md
- Missing source_content raises 404 immediately — no fallback per CONTEXT.md decision

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `test_document_extractor.py` fails to collect due to `pypdf` not installed in venv — this is a pre-existing dependency gap from plan 11-01, not caused by this plan's changes. Logged to deferred items.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SRC-03 fully satisfied: regenerate endpoint reads source_content from SQLite
- Ready for Phase 12 (upload HTTP layer) and Phase 13 (frontend upload)
- Note: pypdf dependency must be installed in venv before 11-01 extraction tests can run — deferred to appropriate phase

---
*Phase: 11-backend-foundation*
*Completed: 2026-03-14*
