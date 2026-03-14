# Roadmap: Super Tutor

## Milestones

- ✅ **v1.0 MVP** - Phases 1-3 (shipped 2026-02-28)
- ✅ **v2.0 In-Session Chat** - Phases 4-5 (shipped 2026-03-01)
- ✅ **v3.0 AgentOS Observability** - Phases 6-7 (shipped 2026-03-07)
- ✅ **v4.0 Agentic Backend Refactor** - Phase 8 (shipped 2026-03-12)
- ✅ **v5.0 API Simplification** - Phases 9-10 (shipped 2026-03-13)
- 🚧 **v6.0 Document Upload** - Phases 11-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) - SHIPPED 2026-02-28</summary>

### Phase 1: URL Session Pipeline
**Goal**: Users can create a study session from any article or documentation URL
**Plans**: 8 plans

Plans:
- [x] 01-01: FastAPI scaffold + SSE session endpoint
- [x] 01-02: URL extraction chain (httpx + trafilatura)
- [x] 01-03: Agno notes agent
- [x] 01-04: SSE progress events
- [x] 01-05: Flashcard agent + on-demand generation
- [x] 01-06: Quiz agent + on-demand generation
- [x] 01-07: localStorage session history (LRU-5)
- [x] 01-08: Human verification gate

### Phase 2: Topic Description Path
**Goal**: Users can create a study session from any topic description without a URL
**Plans**: 4 plans

Plans:
- [x] 02-01: Tavily research agent
- [x] 02-02: Topic session flow wired end-to-end
- [x] 02-03: Amber disclaimer + source links UI
- [x] 02-04: Vague-topic warning system

### Phase 3: Study Experience Polish
**Goal**: Study page delivers a complete, polished tabbed experience with interactive flashcards
**Plans**: 5 plans

Plans:
- [x] 03-01: Tabbed UI (Notes | Flashcards | Quiz)
- [x] 03-02: 3D flashcard flip animation
- [x] 03-03: 4-state tab UI for on-demand generation
- [x] 03-04: Paste-text fallback flow
- [x] 03-05: URL error classification

</details>

<details>
<summary>✅ v2.0 In-Session Chat (Phases 4-5) - SHIPPED 2026-03-01</summary>

### Phase 4: Chat Backend
**Goal**: Backend streams AI chat responses grounded in session notes
**Plans**: 2 plans

Plans:
- [x] 04-01: Stateless Agno chat agent with notes grounding
- [x] 04-02: POST /chat/stream SSE endpoint

### Phase 5: Chat Frontend
**Goal**: Users can open a floating chat panel and have a multi-turn conversation grounded in their session
**Plans**: 3 plans (includes quick tasks 4, 5, 6)

Plans:
- [x] 05-01: Floating chat bubble + sliding panel
- [x] 05-02: fetch + ReadableStream SSE client with 6-turn history cap
- [x] 05-03: Responsive polish (mobile overlay, auto-scroll, resize)

</details>

<details>
<summary>✅ v3.0 AgentOS Observability (Phases 6-7) - SHIPPED 2026-03-07</summary>

### Phase 6: AgentOS Core Integration
**Goal**: All agents produce SQLite traces with token usage, latency, and session isolation
**Plans**: 3 plans

Plans:
- [x] 06-01: FastAPI wrapped with AgentOS (on_route_conflict=preserve_base_app)
- [x] 06-02: All five agents wired with db= for trace capture
- [x] 06-03: session_id threaded through all agent call sites

### Phase 7: Control Plane Connection
**Goal**: Agent traces are queryable from the AgentOS Control Plane at os.agno.com
**Plans**: 2 plans

Plans:
- [x] 07-01: Control Plane verified operational (browser-direct to SQLite)
- [x] 07-02: CTRL-01/02/03 all satisfied; tenacity retry logging added

</details>

<details>
<summary>✅ v4.0 Agentic Backend Refactor (Phase 8) - SHIPPED 2026-03-12</summary>

### Phase 8: Storage and Workflow Foundation
**Goal**: Session data persists server-side in SQLite after creation; Agno-native Workflow replaces plain-Python class
**Plans**: 2 plans

Plans:
- [x] 08-01: SessionWorkflow replaced with Agno Workflow; notes_step writes to session_state
- [x] 08-02: _guard_session() for 404s; SQLite round-trip integration tests

</details>

<details>
<summary>✅ v5.0 API Simplification (Phases 9-10) — SHIPPED 2026-03-13</summary>

### Phase 9: Backend API Simplification
**Goal**: Both API endpoints source notes from SQLite storage — no notes field required in any request body
**Plans**: 1 plan

Plans:
- [x] 09-01: Refactor regenerate endpoint + update tests (API-01, API-02)

### Phase 10: Frontend Cleanup
**Goal**: Frontend never sends notes in API payloads; localStorage notes retention documented
**Plans**: 1 plan

Plans:
- [x] 10-01: Remove notes from regenerate payloads + CLEAN-02 audit (API-03, CLEAN-01, CLEAN-02)

</details>

### 🚧 v6.0 Document Upload (In Progress)

**Milestone Goal:** Users can upload a PDF or Word document and create a full study session from it — same pipeline, third input path.

- [x] **Phase 11: Backend Foundation** - Source content storage wired into all session types; extraction module and regenerate agents updated (completed 2026-03-13)
- [x] **Phase 12: Backend Upload Endpoint** - POST /sessions/upload multipart endpoint wires extraction into the full SSE pipeline (completed 2026-03-14)
- [ ] **Phase 13: Frontend Upload UI** - Third Upload tab on the home page with file input, validation, and error display

## Phase Details

### Phase 11: Backend Foundation
**Goal**: Source content is stored in SQLite for all session types and available to regenerate agents; a shared cleaning utility and document extraction module are in place before any HTTP upload endpoint is built
**Depends on**: Phase 10
**Requirements**: SRC-01, SRC-02, SRC-03, UPLOAD-05, EXTRACT-01, EXTRACT-02, EXTRACT-04, EXTRACT-05
**Success Criteria** (what must be TRUE):
  1. After a URL session completes, `wf.get_session().session_state["source_content"]` contains the trafilatura-extracted text that was passed through `clean_extracted_content()` — confirmed via integration test
  2. After a topic session completes, `session_state["source_content"]` contains the Tavily research text normalised by `clean_extracted_content()` — the same field is present for all session types
  3. `regenerate_section()` loads `source_content` from SQLite (via `build_session_workflow + wf.get_session()`) and passes it to the flashcard and quiz agents as primary generation material — no source_content field in the request body
  4. Calling `extract_document(pdf_bytes, "file.pdf")` on a text-based PDF returns clean plain text without writing anything to disk; calling it on a scanned PDF raises `DocumentExtractionError(error_kind="scanned_pdf")`
  5. Calling `extract_document(docx_bytes, "file.docx")` returns the full text of paragraphs and table cells; extracted text exceeding ~50,000 characters is truncated with a warning marker appended
**Plans**: 3 plans

Plans:
- [ ] 11-01-PLAN.md — TDD: cleaner.py + document_extractor.py + requirements.txt (new extraction module with full unit tests)
- [ ] 11-02-PLAN.md — Wire clean_extracted_content() into URL and topic session paths (chain.py + session_workflow.py)
- [ ] 11-03-PLAN.md — Update regenerate_section() to load source_content from SQLite + update router tests

### Phase 12: Backend Upload Endpoint
**Goal**: Users can POST a PDF or .docx file to `/sessions/upload` and receive a complete study session via the existing SSE pipeline — with the file discarded after extraction and the session stored in SQLite
**Depends on**: Phase 11
**Requirements**: SESSION-01, SESSION-02, SESSION-03
**Success Criteria** (what must be TRUE):
  1. A `curl` request posting a valid text-based PDF to `POST /sessions/upload` produces SSE progress events (including "Extracting document...") and ultimately a session whose notes, flashcards, and quiz are structurally identical to those from URL and topic sessions
  2. A `curl` request posting a valid `.docx` file produces a complete session with the same output structure; the SQLite session record shows `session_type = "upload"` and the original filename as the source field
  3. Posting a scanned/image-only PDF returns a structured error response with `error_kind = "scanned_pdf"` — the workflow is never invoked and no failed session record is written
  4. The existing `POST /sessions` JSON endpoint continues to pass all its existing tests without modification after this phase
**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md — SessionType fix, python-multipart pin, notes_step source persistence (SESSION-02)
- [x] 12-02-PLAN.md — Create upload.py SSE endpoint + register in main.py (SESSION-01, SESSION-02, SESSION-03)
- [x] 12-03-PLAN.md — Write test_upload_router.py + full regression check (SESSION-01, SESSION-02, SESSION-03)

### Phase 13: Frontend Upload UI
**Goal**: Users can select a PDF or .docx file on the home page, validate it client-side, and create a study session from it with the same progress experience as URL and topic sessions; backend upload router extended to accept .docx (audit gap)
**Depends on**: Phase 12
**Requirements**: UPLOAD-01, UPLOAD-02, UPLOAD-03, UPLOAD-04, EXTRACT-03
**Gap Closure**: Closes gaps from v6.0-MILESTONE-AUDIT.md — backend .docx blocker (upload.py line 78), SessionType union missing "upload", loading page incompatible with SSE-first upload flow
**Success Criteria** (what must be TRUE):
  1. `POST /sessions/upload` accepts `.docx` files alongside `.pdf`; a `curl` request posting a valid `.docx` produces SSE progress events and a complete session with `session_type="upload"` — the Phase 12 SC-2 contract is now fully satisfied
  2. The home page shows a third "Upload" tab alongside URL and Topic; selecting it reveals a file input that accepts only `.pdf` and `.docx` files and an optional focus prompt field
  3. Selecting a file larger than 20 MB displays an inline error message before any network request is made; no request is sent to the backend
  4. After selecting a valid file and submitting, the user sees SSE progress messages (including an extraction step specific to upload) and arrives at a complete study session page with notes, flashcards, and quiz working identically to other session types
  5. When the backend returns a scanned PDF error (HTTP 422 `error_kind="scanned_pdf"`), the user sees a specific, actionable error message — not a generic error
  6. The frontend `fetch` call for upload never manually sets `Content-Type` — the browser sets it with the correct `multipart/form-data; boundary=` value automatically
  7. `frontend/src/types/session.ts` `SessionType` union includes `"upload"`; the study page correctly stores and renders upload sessions from localStorage
**Plans**: 4 plans

Plans:
- [ ] 13-01-PLAN.md — Backend patch: extend upload.py ALLOWED_EXTENSIONS to (.pdf, .docx); update test_upload_router.py with .docx acceptance test and .txt rejection test (UPLOAD-02)
- [ ] 13-02-PLAN.md — Frontend types + Upload tab scaffold: add "upload" to SessionType union and buildProgressSteps; add Upload tab to create/page.tsx with file input, 20 MB client-side guard, and loading/page.tsx type cast fix (UPLOAD-01, UPLOAD-03, UPLOAD-04)
- [ ] 13-03-PLAN.md — SSE upload flow: handleUploadSubmit with FormData POST to /sessions/upload (no manual Content-Type), inline SSE consumer, router.push on complete event, error display for pre-stream HTTP errors and SSE error events (UPLOAD-01, UPLOAD-02, UPLOAD-04, EXTRACT-03)
- [ ] 13-04-PLAN.md — End-to-end human verification: automated TypeScript + pytest pre-check, then 9-point manual verification covering all Phase 13 success criteria (UPLOAD-01, UPLOAD-02, UPLOAD-03, UPLOAD-04, EXTRACT-03)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. URL Session Pipeline | v1.0 | 8/8 | Complete | 2026-02-28 |
| 2. Topic Description Path | v1.0 | 4/4 | Complete | 2026-02-28 |
| 3. Study Experience Polish | v1.0 | 5/5 | Complete | 2026-02-28 |
| 4. Chat Backend | v2.0 | 2/2 | Complete | 2026-03-01 |
| 5. Chat Frontend | v2.0 | 3/3 | Complete | 2026-03-01 |
| 6. AgentOS Core Integration | v3.0 | 3/3 | Complete | 2026-03-07 |
| 7. Control Plane Connection | v3.0 | 2/2 | Complete | 2026-03-07 |
| 8. Storage and Workflow Foundation | v4.0 | 2/2 | Complete | 2026-03-12 |
| 9. Backend API Simplification | v5.0 | 1/1 | Complete | 2026-03-13 |
| 10. Frontend Cleanup | v5.0 | 1/1 | Complete | 2026-03-13 |
| 11. Backend Foundation | v6.0 | 3/3 | Complete | 2026-03-13 |
| 12. Backend Upload Endpoint | v6.0 | 3/3 | Complete | 2026-03-14 |
| 13. Frontend Upload UI | 3/4 | In Progress|  | - |
