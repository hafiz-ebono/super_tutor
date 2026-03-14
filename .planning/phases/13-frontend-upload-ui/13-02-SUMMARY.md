---
phase: 13-frontend-upload-ui
plan: "02"
subsystem: ui
tags: [react, typescript, nextjs, file-upload, session-type]

# Dependency graph
requires:
  - phase: 12-backend-upload-endpoint
    provides: POST /sessions/upload SSE endpoint with multipart form; 20 MB size limit; source field on session
provides:
  - SessionType union extended to include 'upload'
  - BASE_STEPS_UPLOAD constant with 'Extracting document...' first step
  - buildProgressSteps handles inputMode='upload' returning correct step sequence
  - Three-tab create page toggle (Article URL, Topic description, Upload file)
  - File input UI with .pdf/.docx accept, 20 MB client-side guard, filename/size display
  - Submit button disabled when Upload tab active and no file selected
  - loading/page.tsx type-safe for inputMode='upload'
affects:
  - 13-03-frontend-upload-submit (Plan 13-03 wires handleSubmit for upload flow using these types and state)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared focus prompt field rendered unconditionally outside tab conditionals — no duplication per tab"
    - "Client-side file size guard resets input value to allow re-selection after oversized file"
    - "InputMode type union extended in create/page.tsx mirrors SessionType extension in session.ts"

key-files:
  created: []
  modified:
    - frontend/src/types/session.ts
    - frontend/src/app/create/page.tsx
    - frontend/src/app/loading/page.tsx

key-decisions:
  - "uploadError and uploadProgressMessage state added in this plan (unused until Plan 13-03) to centralise all upload state declarations in one location"
  - "Focus prompt field confirmed as shared unconditional input — no duplicate added inside Upload section"
  - "handleFileChange resets e.target.value on oversized file so same file path can be re-selected after correction"

patterns-established:
  - "Tab toggle resets opposing state fields on click to prevent stale values crossing tab boundaries"

requirements-completed: [UPLOAD-01, UPLOAD-03, UPLOAD-04]

# Metrics
duration: 2min
completed: 2026-03-14
---

# Phase 13 Plan 02: Frontend Upload UI — Type Foundation and Tab Scaffold Summary

**SessionType union extended to 'upload', three-tab create page with file input, 20 MB client-side guard, and type-safe loading page — all compiling clean with zero TypeScript errors**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-14T09:12:28Z
- **Completed:** 2026-03-14T09:14:23Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Extended `SessionType` and `buildProgressSteps` in session.ts to handle 'upload' input mode with correct "Extracting document..." first step
- Added full Upload tab UI to create/page.tsx — three-tab toggle, file input with accept=".pdf,.docx,...", 20 MB guard with inline error, filename/size display, and disabled submit when no file selected
- Widened inputMode type cast in loading/page.tsx to include 'upload', keeping type system consistent with buildProgressSteps signature

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend session.ts with upload SessionType and buildProgressSteps** - `6d5d193` (feat)
2. **Task 2: Add Upload tab scaffold to create/page.tsx** - `f0c934e` (feat)
3. **Task 3: Widen inputMode cast in loading/page.tsx** - `d92bff2` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `frontend/src/types/session.ts` - Added 'upload' to SessionType union, BASE_STEPS_UPLOAD constant, extended buildProgressSteps signature and body
- `frontend/src/app/create/page.tsx` - Extended InputMode, added upload state variables, handleFileChange with size guard, Upload tab button, file input UI, submit button guard
- `frontend/src/app/loading/page.tsx` - Single-line cast widened to include 'upload'

## Decisions Made
- `uploadError` and `uploadProgressMessage` state variables added in this plan even though Plan 13-03 is responsible for actual submission — centralises all upload-related state in one location to avoid scattered additions
- Focus prompt field confirmed as an unconditional shared field (lines 238-252 of create/page.tsx have no inputMode guard) — no duplicate field added inside the Upload section per plan instruction
- `handleFileChange` resets `e.target.value = ""` on oversized file so the user can re-select the same file path after reducing size

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness
- All type foundations in place; Plan 13-03 can import SessionType='upload', use selectedFile state, and wire up handleSubmit for the multipart fetch + SSE flow
- The shared focusPrompt state variable is correctly wired for inclusion in the upload submission payload Plan 13-03 builds
- Concern: Truncation threshold (50,000 chars) not empirically validated against system prompt token budget — verify during Phase 13 end-to-end test with a large dense-text PDF

---
## Self-Check: PASSED

All files found on disk. All task commits (6d5d193, f0c934e, d92bff2) verified in git log. TypeScript compile exits 0 with zero output.

*Phase: 13-frontend-upload-ui*
*Completed: 2026-03-14*
