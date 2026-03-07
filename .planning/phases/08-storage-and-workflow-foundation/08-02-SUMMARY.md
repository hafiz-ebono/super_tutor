---
phase: 08-storage-and-workflow-foundation
plan: "02"
subsystem: router-workflow-wiring
tags: [agno, workflow, sqlite, session-state, stor-03, wkfl-03, integration-test]
dependency_graph:
  requires: [08-01]
  provides: [stor-03-guard, wkfl-03-round-trip-test, _guard_session]
  affects: [backend/app/routers/sessions.py, backend/tests/test_session_storage.py]
tech_stack:
  added: []
  patterns: [_guard_session helper for STOR-03 404 enforcement, tmp_path fixture for SQLite isolation]
key_files:
  created:
    - backend/tests/test_session_storage.py
  modified:
    - backend/app/routers/sessions.py
decisions:
  - "build_session_workflow + _get_session_db imported into sessions.py to enable _guard_session"
  - "_guard_session raises HTTP 404 with clear message for unknown/expired session_id"
  - "Test uses tmp_path fixture so each test gets a fresh SQLite file — no cross-test contamination"
metrics:
  duration: ~3 min
  completed: 2026-03-07
  tasks_completed: 2
  files_modified: 2
---

# Phase 8 Plan 02: Router Wiring and SQLite Round-Trip Test Summary

**One-liner:** STOR-03 guard added to regenerate_section via _guard_session() helper using build_session_workflow + get_session(), with SQLite round-trip integration test proving WKFL-03 persistence.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Wire run_session_workflow and add STOR-03 guard | 8e87aa6 | backend/app/routers/sessions.py |
| 2 | Write SQLite round-trip integration test | c09edbc | backend/tests/test_session_storage.py |

## What Was Built

### Task 1 — sessions.py Update

Three targeted changes to `backend/app/routers/sessions.py`:

1. **Import update**: Added `build_session_workflow` and `_get_session_db` to the existing `run_session_workflow` import from `app.workflows.session_workflow`.

2. **_guard_session helper**: Added before the router definition. Instantiates a workflow via `build_session_workflow()`, calls `wf.get_session(session_id=session_id)`, and raises `HTTPException(404)` with a clear message if `None` is returned. This implements STOR-03.

3. **regenerate_section guard**: Added `_guard_session(session_id)` call after the section validation check in `regenerate_section`. Phase 10 will use stored notes from SQLite instead of client-supplied `body.notes`; for now, this validates the session exists before proceeding.

### Task 2 — SQLite Round-Trip Integration Test

Created `backend/tests/test_session_storage.py` with 3 tests:

- **`test_session_state_round_trip`**: Builds Workflow with minimal `_write_test_state` executor, runs `workflow.run()`, then reads `get_session_state()` from a fresh Workflow instance. Verifies all 4 fields (`notes`, `tutoring_type`, `session_type`, `sources`) persisted to SQLite. This is the WKFL-03 acceptance test.

- **`test_get_session_returns_none_for_unknown_id`**: Verifies `get_session()` returns `None` for a session_id that was never written. This is the foundation for `_guard_session()` correctness.

- **`test_session_db_uses_separate_id`**: Verifies `id='super_tutor_sessions'` (STOR-02: separate from traces DB with `id='super_tutor_traces'`).

All 3 tests passed. No real notes agent called — all tests use the minimal `_write_test_state` executor with fixed values and `tmp_path` for SQLite isolation.

## Deviations from Plan

None - plan executed exactly as written. The 08-01 deviation (router update in Task 2) had already been applied, so Task 1 here only needed to add the missing imports (`build_session_workflow`, `_get_session_db`) and the `_guard_session` helper.

## Verification Results

All plan verification checks passed:
- `from app.routers.sessions import router; from app.workflows.session_workflow import run_session_workflow, build_session_workflow; print('wiring OK')` — OK
- `grep -n "run_session_workflow" backend/app/routers/sessions.py` — matches on import (line 13) and async for call (line 191)
- `grep -n "_guard_session" backend/app/routers/sessions.py` — matches definition (line 35) and call site (line 244)
- `grep -rn "build_workflow" backend/app/` — no source file matches (only .pyc cache)
- Full test suite: 10 passed, 1 pre-existing failure (`test_agent_api_key_defaults_to_empty_string` — local `.env` overrides the empty-string default; confirmed pre-existing since 08-01)

## Self-Check: PASSED

Files exist:
- backend/app/routers/sessions.py — FOUND
- backend/tests/test_session_storage.py — FOUND

Commits exist:
- 8e87aa6 (feat(08-02): wire run_session_workflow and add STOR-03 guard to sessions.py) — FOUND
- c09edbc (test(08-02): add SQLite round-trip integration tests for WKFL-03 and STOR-03) — FOUND
