# Requirements: Super Tutor

**Defined:** 2026-02-18
**Core Value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v1 Requirements

### Session Creation

- [x] **SESS-01**: User can create a session by providing an article/doc URL and a focus prompt describing what to study
- [ ] **SESS-02**: User can create a session by providing a topic description (AI performs deep web research to generate source material)
- [x] **SESS-03**: User selects a tutoring type (Micro Learning / Teaching a Kid / Advanced) before generating a session; this adapts tone and complexity of all generated content
- [x] **SESS-04**: If URL scraping fails (paywall, empty page, invalid URL), user is shown a specific error message and offered a paste-text fallback to continue
- [x] **SESS-05**: User sees step-by-step progress feedback during AI generation (e.g., "Extracting content... Generating notes... Creating flashcards... Building quiz...")

### Content Generation

- [x] **GEN-01**: AI generates structured notes from the session content, adapted to the selected tutoring type's tone and complexity
- [x] **GEN-02**: AI generates flashcards from the session content, adapted to the selected tutoring type's tone and complexity
- [x] **GEN-03**: AI generates a multiple-choice quiz (4 options per question, one correct answer) from the session content, adapted to the selected tutoring type

### Study Experience

- [x] **STUDY-01**: All study materials (notes, flashcards, quiz) are presented on a single page with tab navigation (Notes | Flashcards | Quiz)
- [ ] **STUDY-02**: Flashcards have an interactive flip animation — user clicks to reveal the answer

### AI Infrastructure

- [x] **AGENT-01**: All AI agents (URL extraction, topic research, notes generation, flashcard generation, quiz generation) are built with the Agno framework
- [x] **AGENT-02**: AI provider, model, and API key are configurable via environment variables or config file — switching providers (OpenAI, Anthropic, Groq, etc.) or models requires only a config change, no code changes

## v2 Requirements

### AI Chat

- **CHAT-01**: In-session AI chat grounded in session content (chat panel knows the material being studied)
- **CHAT-02**: Chat responses stream in real-time via SSE

### Study Enhancements

- **STUDY-03**: Quiz answer explanations (why the correct answer is right, tied to source material)
- **STUDY-04**: Keyboard navigation for flashcards and quiz
- **STUDY-05**: Copy-to-clipboard for notes and individual flashcards

### Persistence

- **AUTH-01**: User can create an account to save sessions and track progress across visits
- **AUTH-02**: User session persists across browser refresh (logged-in users)
- **PROG-01**: Cross-session completion tracking (quiz scores, flashcard history)
- **PROG-02**: Shareable session links with TTL (requires Redis)

## Out of Scope

| Feature | Reason |
|---------|--------|
| User accounts (v1) | Adds 2-4 weeks of infrastructure; zero-friction is a core v1 value |
| YouTube / video URL input | Separate transcription pipeline (Whisper); changes extraction architecture significantly |
| Export to PDF / Anki | Power-user feature; add copy-to-clipboard first |
| Social features (share, comments) | Requires accounts; out of scope for v1 |
| Mobile app | Web-first; defer until web product is validated |
| Spaced repetition scheduling | Requires accounts + scheduling logic; cannot exist without persistence |
| LangChain / LlamaIndex | Abstraction overhead not justified; Agno chosen instead |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SESS-01 | Phase 1 | Complete |
| SESS-02 | Phase 2 | Pending |
| SESS-03 | Phase 1 | Complete (01-01) |
| SESS-04 | Phase 1 | Complete |
| SESS-05 | Phase 1 | Complete |
| GEN-01 | Phase 1 | Complete |
| GEN-02 | Phase 1 | Complete |
| GEN-03 | Phase 1 | Complete |
| STUDY-01 | Phase 1 | Complete |
| STUDY-02 | Phase 3 | Pending |
| AGENT-01 | Phase 1 | Complete (01-01) |
| AGENT-02 | Phase 1 | Complete (01-01) |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-18*
*Last updated: 2026-02-18 — AGENT-01, AGENT-02, SESS-03 marked complete after 01-01 execution*
