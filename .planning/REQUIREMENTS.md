# Requirements: Super Tutor

**Defined:** 2026-03-07
**Core Value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v4.0 Requirements

Requirements for the Agentic Backend Refactor milestone. Agno-native Workflow and Team primitives with SQLite session storage, plus opt-in eager generation.

### Storage Infrastructure

- [x] **STOR-01**: Backend stores session data (notes, tutoring_type, session_type, sources) in SQLite keyed by session_id after session creation completes
- [x] **STOR-02**: Session storage uses a separate SQLite file from AgentOS traces, configurable via env var (`SESSION_DB_PATH`)
- [x] **STOR-03**: Request to regenerate or chat with an expired/unknown session_id returns a clear error to the client

### Workflow Refactor

- [x] **WKFL-01**: `SessionWorkflow` is an `agno.workflow.Workflow` subclass (not a plain Python class workaround)
- [x] **WKFL-02**: Workflow `run()` writes extracted content, notes, tutoring_type, and sources to `session_state` after notes generation
- [x] **WKFL-03**: Session data written in `run()` is readable by subsequent requests using the same session_id (SQLite round-trip verified)

### Team Integration

- [ ] **TEAM-01**: `TutorTeam` (`agno.team.Team`) coordinates notes, flashcard, and quiz agents in coordinate mode
- [ ] **TEAM-02**: User can opt into eager generation (generate notes + flashcards + quiz during session creation) via a checkbox on the create page
- [ ] **TEAM-03**: If eager generation is selected and flashcard/quiz agents fail but notes succeed, the session completes with notes only — no full session abort
- [ ] **TEAM-04**: Failed eager-generated sections fall back silently to on-demand generation (existing Generate button remains functional)

### API Simplification

- [ ] **API-01**: Flashcard/quiz regenerate endpoint loads notes from storage — client no longer sends notes in request body
- [ ] **API-02**: Chat endpoint loads notes and tutoring_type from storage — client no longer sends notes in request body
- [ ] **API-03**: Frontend stops sending notes in regenerate and chat requests

## v5.0 Requirements

Deferred to future milestone.

### Team Enhancements

- **TEAM-05**: Session expiry / TTL — timestamp stored in session_state, router warns on stale sessions
- **TEAM-06**: Notes truncation guard — single place to cap note length now that notes come from storage

### Persistence Extensions

- **PERS-01**: Chat history survives page refresh (server-side session storage for chat turns)
- **PERS-02**: User can return to a previous session and resume studying

## Out of Scope

| Feature | Reason |
|---------|--------|
| User accounts / auth | Core value is no-friction; deferred |
| PostgreSQL storage | Async Postgres not yet in Agno; SQLite sufficient at current scale |
| YouTube / video URL support | Text-only content source |
| Mobile app | Web-first |
| Export to PDF / Anki | Study in-app only |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| STOR-01 | Phase 8 | Complete |
| STOR-02 | Phase 8 | Complete |
| STOR-03 | Phase 8 | Complete |
| WKFL-01 | Phase 8 | Complete |
| WKFL-02 | Phase 8 | Complete |
| WKFL-03 | Phase 8 | Complete |
| TEAM-01 | Phase 9 | Pending |
| TEAM-02 | Phase 9 | Pending |
| TEAM-03 | Phase 9 | Pending |
| TEAM-04 | Phase 9 | Pending |
| API-01 | Phase 10 | Pending |
| API-02 | Phase 10 | Pending |
| API-03 | Phase 10 | Pending |

**Coverage:**
- v4.0 requirements: 13 total
- Mapped to phases: 13
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-07*
*Last updated: 2026-03-07 after v4.0 roadmap creation*
