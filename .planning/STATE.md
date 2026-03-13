# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-13 after v6.0 milestone start)

**Core value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.
**Current focus:** v6.0 Document Upload — Phase 11 (Backend Foundation)

## Current Position

Phase: 11 of 13 (Backend Foundation)
Plan: 3 of 4 complete
Status: In progress
Last activity: 2026-03-14 — Completed 11-03: regenerate_section() reads source_content from SQLite (SRC-03)

Progress: [██████████░░░] 77% (10/13 phases complete across all milestones; Phase 11 in progress 3/4 plans)

## Performance Metrics

**Velocity:**
- Total plans completed: 28 (v1.0: 17, v2.0: 4, v3.0: 5, v4.0: 2, v5.0: 2; quick tasks excluded)
- Average duration: ~4 min
- Total execution time: ~111 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-url-session-pipeline | 8 | ~38min | ~5min |
| 02-topic-description-path | 4 | ~20min | ~5min |
| 03-study-experience-polish | 5 | ~10min | ~2min |
| 04-chat-backend | 2 | ~4min | ~2min |
| 05-chat-frontend | 3 | ~6min | ~2min |
| 06-agentos-core-integration | 3 | ~11min | ~4min |
| 07-control-plane-connection | 2 | ~13min | ~6min |
| 08-storage-and-workflow-foundation | 2 | ~5min | ~2.5min |
| 09-backend-api-simplification | 1 | ~2min | ~2min |
| 10-frontend-cleanup | 1 | ~1min | ~1min |

**Recent Trend:**
- Last 5 plans: ~4min, ~2min, ~2min, ~1min, ~1min
- Trend: Stable (small focused plans executing fast)

*Updated after each plan completion*

## Accumulated Context

### Decisions

All decisions logged in PROJECT.md Key Decisions table (fully updated after v5.0 archive).

**11-01 decisions:**
- Module-level imports used for PdfReader/Document (not deferred) to enable unittest.mock patch targets at app.extraction.document_extractor.PdfReader
- NFKC does not convert fancy quotes (U+201C/D) to ASCII — they are canonical Unicode; tests updated accordingly

**11-03 decisions:**
- source_content (not notes) is the authoritative input for flashcard/quiz regeneration — satisfies SRC-03
- No 'Content:\n' framing prefix — input_text = source_content raw text per CONTEXT.md decision
- No graceful fallback — missing source_content raises HTTP 404 immediately per CONTEXT.md

Key architectural facts for v6.0:
- `asyncio.to_thread()` required for all synchronous extraction calls in async FastAPI handlers (pypdf and python-docx are blocking; same pattern as existing workflow.run())
- `document_extractor.py` must accept `bytes` and return `str` — never touch the filesystem
- `POST /sessions/upload` is a separate multipart endpoint from `POST /sessions` JSON — cannot combine content types in FastAPI
- Do NOT set `Content-Type: multipart/form-data` manually in frontend fetch — browser sets it with correct boundary when FormData is the body
- File size decision: use 20 MB (client-side guard via EXTRACT-03) — consistent with FEATURES.md recommendation
- Truncation threshold: ~50,000 characters before handoff to notes agent (EXTRACT-05)
- `source_content` stored in `session_state` for ALL session types (URL, topic, upload) — canonical read pattern is `build_session_workflow() + wf.get_session()` (same as notes)
- `clean_extracted_content()` shared utility called by BOTH the URL path (sessions.py) AND document_extractor.py — single normalisation layer
- Phase 11 touches existing code (SessionWorkflow, sessions.py URL path, regenerate endpoint) AND introduces new extraction code — highest change surface of v6.0
- Phase 12 is the upload HTTP layer only — extractor is a pure function already tested in Phase 11
- Phase 13 is pure frontend — backend contract is stable before this phase begins
- [Phase 11-backend-foundation]: Paste path uses source_type='document' (strip HTML tags) while URL/research paths use source_type='url' (preserve markdown)
- [Phase 11-backend-foundation]: No test file changes needed in 11-02 — ASCII repeat string fixtures round-trip through cleaner unchanged

### Pending Todos

None.

### Blockers/Concerns

- Truncation threshold (50,000 chars) not empirically validated against system prompt token budget — verify during Phase 13 end-to-end test with a large dense-text PDF.
- Existing URL path in sessions.py must be updated to store `source_content` in Phase 11 without breaking the existing URL session pipeline — regression risk; add/update integration tests.

## Session Continuity

Last session: 2026-03-14
Stopped at: Completed 11-03-PLAN.md (regenerate_section uses source_content from SQLite)
Resume file: None
