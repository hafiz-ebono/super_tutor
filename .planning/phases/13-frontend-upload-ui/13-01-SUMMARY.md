---
phase: 13-frontend-upload-ui
plan: "01"
subsystem: api
tags: [fastapi, sse, file-upload, docx, testing]

# Dependency graph
requires:
  - phase: 12-backend-upload-endpoint
    provides: POST /sessions/upload SSE endpoint with .pdf-only extension check

provides:
  - upload.py ALLOWED_EXTENSIONS tuple accepting both .pdf and .docx
  - 6-test suite covering PDF SSE, .docx SSE, .txt rejection, scanned PDF, oversized file, SC4 regression

affects:
  - 13-frontend-upload-ui (remaining plans: frontend can now safely send .docx files to backend)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-level ALLOWED_EXTENSIONS tuple for multi-format extension guards in FastAPI routers"

key-files:
  created: []
  modified:
    - backend/app/routers/upload.py
    - backend/tests/test_upload_router.py

key-decisions:
  - "ALLOWED_EXTENSIONS = ('.pdf', '.docx') placed as module-level constant immediately after MAX_BYTES, before the router decorator"
  - "endswith(ALLOWED_EXTENSIONS) tuple form replaces single-string endswith('.pdf') — Python built-in, no regex needed"
  - ".txt used as the rejected format in test_unsupported_format_returns_400 (not .docx, which is now accepted)"

patterns-established:
  - "Multi-extension guard: endswith(ALLOWED_EXTENSIONS) with a module-level tuple — extend tuple to add new formats"

requirements-completed:
  - UPLOAD-02

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 13 Plan 01: Backend .docx Support Patch Summary

**Backend upload router extended to accept .docx alongside .pdf via ALLOWED_EXTENSIONS tuple, with updated tests adding a .docx SSE happy-path and correcting the rejection test to use .txt**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-14T09:12:18Z
- **Completed:** 2026-03-14T09:14:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `ALLOWED_EXTENSIONS = (".pdf", ".docx")` constant to upload.py and replaced the single-format `.endswith(".pdf")` guard
- Updated error message from "Only PDF files are supported" to "Only PDF and Word (.docx) files are supported"
- Renamed `test_non_pdf_returns_400` to `test_unsupported_format_returns_400`, switching the rejected file from `.docx` to `.txt`
- Added `test_valid_docx_produces_sse_stream` mirroring the existing PDF happy-path test — 6 tests total, all passing
- Full backend suite (121 tests) passes with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Patch upload.py extension check to accept .pdf and .docx** - `4a610c7` (feat)
2. **Task 2: Update test_upload_router.py — flip .docx rejection test, add .docx acceptance test** - `f36f7ed` (test)

## Files Created/Modified

- `backend/app/routers/upload.py` - Added ALLOWED_EXTENSIONS tuple; replaced single-format extension guard; updated docstring and error message
- `backend/tests/test_upload_router.py` - Renamed/updated rejection test to use .txt; added test_valid_docx_produces_sse_stream

## Decisions Made

- `ALLOWED_EXTENSIONS` positioned as module-level constant (after `MAX_BYTES`) for import-time visibility and easy patching in tests
- Python's built-in `str.endswith(tuple)` form used — no regex, no external dependency
- `.txt` chosen as the canonical "unsupported format" test input (not `.docx`, which is now valid)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend now accepts both `.pdf` and `.docx` uploads — UPLOAD-02 requirement satisfied
- Frontend (remaining Phase 13 plans) can safely send `.docx` FormData to `POST /sessions/upload`
- No blockers for frontend UI implementation

---
*Phase: 13-frontend-upload-ui*
*Completed: 2026-03-14*

## Self-Check: PASSED

- FOUND: backend/app/routers/upload.py
- FOUND: backend/tests/test_upload_router.py
- FOUND: .planning/phases/13-frontend-upload-ui/13-01-SUMMARY.md
- FOUND: commit 4a610c7 (feat: upload.py ALLOWED_EXTENSIONS)
- FOUND: commit f36f7ed (test: .docx acceptance tests)
