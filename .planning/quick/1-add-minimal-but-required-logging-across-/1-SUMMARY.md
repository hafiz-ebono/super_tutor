---
phase: quick-1-logging
plan: "01"
subsystem: backend-observability
tags: [logging, observability, debugging, stdlib]
dependency_graph:
  requires: []
  provides: [structured-logging-across-all-backend-layers]
  affects: [backend/app/main.py, backend/app/agents/model_factory.py, backend/app/routers/sessions.py, backend/app/workflows/session_workflow.py, backend/app/extraction/chain.py, backend/app/agents/research_agent.py]
tech_stack:
  added: []
  patterns: [stdlib-logging-basicConfig, named-module-loggers, perf_counter-timing]
key_files:
  created: []
  modified:
    - backend/app/main.py
    - backend/app/agents/model_factory.py
    - backend/app/routers/sessions.py
    - backend/app/workflows/session_workflow.py
    - backend/app/extraction/chain.py
    - backend/app/agents/research_agent.py
decisions:
  - "logging.basicConfig called once in main.py; all module loggers inherit root config via named hierarchy (super_tutor.*)"
  - "model_factory uses DEBUG level (not INFO) to avoid per-agent-instantiation noise — startup log in main.py already covers config once"
  - "Stream opened log placed in stream_session() scope (before event_generator closure) so session_id is reliably in scope"
metrics:
  duration: ~8min
  completed: 2026-02-27
  tasks_completed: 2
  files_modified: 6
---

# Quick Task 1: Add Minimal but Required Logging Summary

**One-liner:** stdlib logging wired across all six backend layers — startup, session lifecycle, agent step timing, extraction outcomes, and all error paths — using a single basicConfig in main.py with named module loggers inheriting root config.

## What Was Built

Structured observability logging added to the entire backend pipeline using only Python's stdlib `logging` and `time` modules (no new dependencies).

### Log coverage per layer

| Layer | Logger name | Events logged |
|-------|-------------|---------------|
| main.py | super_tutor.main | App start (provider/model/origins), shutdown |
| model_factory.py | super_tutor.model_factory | Model resolved (DEBUG per agent instantiation) |
| sessions.py | super_tutor.sessions | Session created (id/input_type/tutoring_type), stream opened, stream complete, extraction warnings, research failures (ERROR+exc_info), workflow errors (ERROR+exc_info) |
| session_workflow.py | super_tutor.workflow | Step start/done with elapsed seconds for notes/flashcards/quiz; title generation DEBUG; title fallback WARNING; step error (ERROR+exc_info) |
| extraction/chain.py | super_tutor.extraction | Extraction success per layer (jina/trafilatura/playwright) with char count; all-layers-failed WARNING |
| research_agent.py | super_tutor.research | Research start (topic/focus), research done (elapsed/content_chars/sources) |

### Log format

All lines use the uniform format configured in main.py:
```
YYYY-MM-DD HH:MM:SS LEVEL super_tutor.module — message key=value ...
```

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Logging config in main.py and model_factory.py | c8d6c8d | backend/app/main.py, backend/app/agents/model_factory.py |
| 2 | Runtime event logging — sessions, workflow, extraction, research | 9cf6873 | backend/app/routers/sessions.py, backend/app/workflows/session_workflow.py, backend/app/extraction/chain.py, backend/app/agents/research_agent.py |

## Decisions Made

1. **Single basicConfig in main.py** — Called once at module level so all loggers in the process tree inherit the same format and level. Named loggers (`super_tutor.*`) allow per-module filtering without extra config.

2. **model_factory at DEBUG level** — `get_model()` is called once per agent instantiation (notes, flashcards, quiz, title, research — 5 times per session). Using DEBUG instead of INFO keeps the default log stream clean while still being inspectable with `--log-level debug`.

3. **Stream opened log in stream_session() scope** — Placed immediately after `PENDING_STORE.pop(session_id)` (outside the async generator closure) so it fires even if the event generator never runs. The `session_id` closure variable is still accessible inside `event_generator()`.

4. **perf_counter for step timing** — `time.perf_counter()` is the right tool for elapsed wall-clock timing of synchronous agent calls inside the workflow. Reset per-step with `_t` variable reuse.

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `python -c "from app.main import app; print('ok')"` from `backend/` — passes, no ImportError
- All six modified files import cleanly: `from app.routers.sessions import router; from app.workflows.session_workflow import SessionWorkflow; from app.extraction.chain import extract_content; from app.agents.research_agent import run_research; print('imports ok')` — confirmed
- No `print()` calls added — grep confirms zero matches across all six files
- No new packages added to requirements.txt (stdlib `logging` and `time` only)

## Self-Check: PASSED

Files exist:
- backend/app/main.py: FOUND
- backend/app/agents/model_factory.py: FOUND
- backend/app/routers/sessions.py: FOUND
- backend/app/workflows/session_workflow.py: FOUND
- backend/app/extraction/chain.py: FOUND
- backend/app/agents/research_agent.py: FOUND

Commits exist:
- c8d6c8d: FOUND (feat(quick-1-logging-01): add logging basicConfig and startup lifespan log)
- 9cf6873: FOUND (feat(quick-1-logging-02): add runtime lifecycle logs across sessions, workflow, extraction, research)
