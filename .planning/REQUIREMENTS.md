# Requirements: Super Tutor

**Defined:** 2026-03-13
**Core Value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v6.0 Requirements

### Source Content Storage (cross-cutting — all session types)

- [x] **SRC-01**: All session types (URL, topic, upload) store `source_content` in SQLite session state after extraction
- [x] **SRC-02**: A shared `clean_extracted_content()` utility normalises extracted text before it is stored — applied to both URL-extracted text (trafilatura output) and document-extracted text (pypdf/.docx output)
- [x] **SRC-03**: Flashcard and quiz regenerate agents load `source_content` from SQLite as primary generation material (replaces notes-only grounding for generation tasks)

### Upload Input Path

- [x] **UPLOAD-01**: User can upload a PDF file from the home page and create a study session from it
- [x] **UPLOAD-02**: User can upload a Word (.docx) file from the home page and create a study session from it
- [x] **UPLOAD-03**: Upload is a third selectable tab on the home page alongside URL and Topic
- [x] **UPLOAD-04**: User can provide an optional focus prompt alongside the uploaded file (same as URL path)
- [x] **UPLOAD-05**: File is processed in memory and discarded — not stored on server

### Extraction & Error Handling

- [x] **EXTRACT-01**: Backend extracts plain text from uploaded PDF using pypdf (memory-only, no disk write)
- [x] **EXTRACT-02**: Backend extracts plain text from uploaded .docx using python-docx (memory-only, no disk write)
- [ ] **EXTRACT-03**: Files larger than 20 MB are rejected client-side before upload with a clear error message
- [x] **EXTRACT-04**: Scanned/image-only PDFs (near-zero extracted text) return a specific error message to the user
- [x] **EXTRACT-05**: Documents whose extracted text exceeds ~50,000 characters are truncated with a visible warning advising the user to upload a specific chapter or section

### Session Output

- [x] **SESSION-01**: Upload session produces the same notes, flashcards, and quiz output as URL and topic sessions
- [x] **SESSION-02**: Upload session stores `session_type = "upload"` and filename as source in SQLite (same session_id contract)
- [x] **SESSION-03**: User sees SSE progress events during upload session creation (same progress UX as URL and topic paths)

## Future Requirements

### Large Document Support

- **LARGE-01**: RAG-based agent for documents exceeding extraction limits — Agno PDFKnowledgeBase + per-session vector namespace
- **LARGE-02**: Hierarchical summarisation for very long documents (chunk → summarise → synthesise)

### Enhanced Grounding

- **GROUND-01**: Chat agent optionally references `source_content` in addition to notes for deeper factual grounding (deferred — high per-turn token cost)

### Additional File Types

- **FILES-01**: Plain text (.txt) file upload support
- **FILES-02**: Markdown (.md) file upload support

### Enhanced Extraction

- **ENHANCE-01**: Structure-preserving .docx extraction (headings, sections) for improved notes quality
- **ENHANCE-02**: Focus-guided truncation — semantic search to find most relevant sections when content exceeds limit

## Out of Scope

| Feature | Reason |
|---------|--------|
| OCR for scanned PDFs | ~200 MB of dependencies (Tesseract), unreliable output; clear error + Topic tab is the better UX |
| Legacy .doc (Word 97–2003) | Requires `antiword` or COM automation; .docx covers modern use cases |
| Multi-file upload | Single document per session keeps the session model simple |
| Server-side file storage | Stateless design is core — extract and discard |
| RAG / vector store | Deferred to future milestone; plain extraction covers 95% of real study documents |
| Chat grounded on source_content | Deferred (GROUND-01) — notes are sufficient for chat and keep per-turn token cost low |
| YouTube / video upload | Text-based content only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SRC-01 | Phase 11 | Complete |
| SRC-02 | Phase 11 | Complete |
| SRC-03 | Phase 11 | Complete |
| UPLOAD-01 | Phase 13 | Complete |
| UPLOAD-02 | Phase 13 | Complete |
| UPLOAD-03 | Phase 13 | Complete |
| UPLOAD-04 | Phase 13 | Complete |
| UPLOAD-05 | Phase 11 | Complete |
| EXTRACT-01 | Phase 11 | Complete |
| EXTRACT-02 | Phase 11 | Complete |
| EXTRACT-03 | Phase 13 | Pending |
| EXTRACT-04 | Phase 11 | Complete |
| EXTRACT-05 | Phase 11 | Complete |
| SESSION-01 | Phase 12 | Complete |
| SESSION-02 | Phase 12 | Complete |
| SESSION-03 | Phase 12 | Complete |

**Coverage:**
- v6.0 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-13*
*Last updated: 2026-03-14 after v6.0 roadmap revision — EXTRACT-01, EXTRACT-02, EXTRACT-04, EXTRACT-05 moved to Phase 11 (document_extractor.py and safety guards belong to backend foundation, not upload endpoint)*
