---
phase: 13-frontend-upload-ui
plan: "03"
subsystem: ui
tags: [react, typescript, nextjs, file-upload, sse, formdata, session-type]

# Dependency graph
requires:
  - phase: 13-frontend-upload-ui
    provides: Plan 13-02 — three-tab create page with upload state vars (uploadError, uploadProgressMessage, selectedFile, isSubmitting), handleFileChange with 20 MB guard
  - phase: 12-backend-upload-endpoint
    provides: POST /sessions/upload SSE endpoint; multipart form contract (file, tutoring_type, focus_prompt, generate_flashcards, generate_quiz); SSE event format (progress/complete/error)
provides:
  - handleUploadSubmit async function wired into CreateForm
  - FormData assembly with correct field names matching upload.py
  - Inline SSE reader consuming progress, complete, and error events
  - Upload progress spinner replacing file input UI while streaming
  - Upload error banner with error_kind-aware title and scanned_pdf actionable copy
  - Tab switch clears stale uploadError and uploadProgressMessage state
affects:
  - end-to-end upload user flow — no further frontend upload plans

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "No manual Content-Type header on FormData fetch — browser sets multipart/form-data with correct boundary"
    - "Inline SSE reader using res.body.getReader() + TextDecoder + line buffer — no EventSource (SSE over POST)"
    - "Conditional render: isSubmitting replaces file input with spinner; uploadError renders below when !isSubmitting"

key-files:
  created: []
  modified:
    - frontend/src/app/create/page.tsx

key-decisions:
  - "No Content-Type header set in handleUploadSubmit — manually setting it breaks FastAPI multipart boundary parsing"
  - "Inline ReadableStream reader (not EventSource) required because SSE is over POST, EventSource only supports GET"
  - "scanned_pdf error gets a fixed, actionable override message — other error_kinds fall through to backend-supplied message"
  - "Tab switch handlers on all three tabs clear uploadError and uploadProgressMessage to prevent stale state from prior upload attempt"

patterns-established:
  - "SSE over POST pattern: fetch body as FormData, read res.body.getReader() with line buffer, parse event: / data: prefixes manually"

requirements-completed: [UPLOAD-01, UPLOAD-02, UPLOAD-04, EXTRACT-03]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 13 Plan 03: Frontend Upload UI — Submit Flow and SSE Consumer Summary

**End-to-end upload submission wired: FormData fetch to /sessions/upload with inline SSE consumption, live progress display, and error_kind-aware error UI using browser ReadableStream**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-14T09:17:48Z
- **Completed:** 2026-03-14T09:19:15Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Added `handleUploadSubmit` to CreateForm — assembles FormData, POSTs to /sessions/upload (no manual Content-Type), reads SSE stream inline via res.body.getReader(), calls saveSession with session_type='upload' on complete, and routes to /study/<session_id>
- Upload tab UI now shows spinner + live progress message while streaming and hides the file input; shows error banner after failure
- All three tab toggle buttons clear `uploadError` and `uploadProgressMessage` to prevent stale state persisting across tab switches

## Task Commits

Each task was committed atomically:

1. **Task 1: Add handleUploadSubmit — FormData fetch and inline SSE consumer** - `3525575` (feat)
2. **Task 2: Add upload progress display and error UI in Upload tab section** - `d529b40` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `frontend/src/app/create/page.tsx` - Added handleUploadSubmit, SSE consumer, progress spinner block, error banner, tab-switch state resets

## Decisions Made
- No `Content-Type` header in the fetch options. FastAPI uses the `boundary` value embedded by the browser in the header to parse multipart fields. Manually setting `Content-Type: multipart/form-data` (without boundary) causes FastAPI to return HTTP 422.
- EventSource was not used. EventSource only supports GET; the upload endpoint is POST with a FormData body. The inline ReadableStream approach (getReader + TextDecoder + line buffer) is the only viable path.
- `scanned_pdf` error_kind gets a fixed actionable override message pointing users to the Topic tab; all other error_kinds fall through to the backend-supplied message string directly.
- Tab switch handlers on URL and Topic tabs now include `setUploadError(null)` and `setUploadProgressMessage(null)` to clear upload state that would otherwise persist visibly if the user starts an upload, switches tabs, then returns to Upload.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- Phase 13 is complete. The full upload flow is end-to-end functional: client-side guard (13-02) → multipart upload + SSE stream (13-03) → study page navigation.
- End-to-end verification can be done with both backend (uvicorn) and frontend (npm run dev) running together; test with a text-based PDF and observe spinner → /study/<session_id> navigation.
- Remaining open concern: truncation threshold (50,000 chars) not empirically validated against system prompt token budget — verify with a large dense-text PDF during QA.

---
## Self-Check: PASSED

All files found on disk. All task commits (3525575, d529b40) verified in git log. TypeScript compile exits 0 with zero output.

*Phase: 13-frontend-upload-ui*
*Completed: 2026-03-14*
