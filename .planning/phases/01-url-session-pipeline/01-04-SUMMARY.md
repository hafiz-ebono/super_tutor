---
phase: 01-url-session-pipeline
plan: 04
subsystem: agents
tags: [python, agno, openai, workflow, streaming]

requires:
  - phase: 01-01
    provides: model_factory.get_model(), personas.PERSONAS dict

provides:
  - Three Agno agent builders (notes, flashcard, quiz) with persona injection
  - SessionWorkflow class with run() sync generator yielding progress events
  - _parse_json_safe() for robust LLM JSON output handling

affects: [01-05-fastapi-sse-endpoint]

tech-stack:
  added: [agno>=2.1.1, openai]
  patterns: [agent-builder-factory, sync-generator-streaming, defensive-json-parsing]

key-files:
  created:
    - backend/app/agents/notes_agent.py
    - backend/app/agents/flashcard_agent.py
    - backend/app/agents/quiz_agent.py
    - backend/app/workflows/session_workflow.py

key-decisions:
  - "SessionWorkflow does NOT inherit from agno.workflow.Workflow — agno 2.1.1 has incompatible event-based API (WorkflowStartedEvent etc.) vs plan's RunResponse pattern; plain Python class preserves identical interface for SSE endpoint"
  - "RunResponse is a plain dataclass with .content and .event attributes — no agno import needed"
  - "Flashcard and quiz agents include 'Return ONLY valid JSON, no markdown fences' to prevent LLM wrapping output in prose"

requirements-completed:
  - AGENT-01
  - GEN-01
  - GEN-02
  - GEN-03
  - SESS-05

duration: 6min
completed: 2026-02-19
---

# Phase 01 Plan 04: Agno Agents + SessionWorkflow Summary

**Three Agno agent builders (notes, flashcard, quiz) with tutoring-type persona injection + SessionWorkflow sync generator yielding SSE-compatible progress events.**

## Performance

- **Duration:** 6 min
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Three agent builders work for all 3 tutoring types without API keys (import-only verified)
- SessionWorkflow.run() yields string RunResponses for progress, dict RunResponse for completion
- _parse_json_safe() handles both raw JSON and markdown-fenced JSON from LLMs

## Task Commits

1. **Task 1: Three agent builders** - `6dbf83a` (feat)
2. **Task 2: SessionWorkflow** - `df32062` (feat)

## Files Created/Modified
- `backend/app/agents/notes_agent.py` — build_notes_agent(tutoring_type) → Agno Agent
- `backend/app/agents/flashcard_agent.py` — build_flashcard_agent(tutoring_type) → Agno Agent
- `backend/app/agents/quiz_agent.py` — build_quiz_agent(tutoring_type) → Agno Agent
- `backend/app/workflows/session_workflow.py` — SessionWorkflow + RunResponse + build_workflow()

## Deviations from Plan

**[Rule 4 - Architectural] agno 2.1.1 Workflow API incompatibility**
Found during: Task 2
Issue: agno.run.workflow in 2.1.1 uses event-based streaming (WorkflowStartedEvent, WorkflowCompletedEvent etc.) — no RunResponse or RunEvent classes as the plan assumed
Fix: SessionWorkflow is a plain Python class with a custom RunResponse dataclass; run() generator interface is identical to what plan 01-05 expects
Files modified: backend/app/workflows/session_workflow.py
Impact: None — SSE endpoint interface unchanged; all plan 01-05 patterns still work

Total deviations: 1 architectural (auto-resolved as equivalent interface).

## Self-Check: PASSED
