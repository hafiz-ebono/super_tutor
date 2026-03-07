# Roadmap: Super Tutor

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3 (shipped 2026-02-28)
- ✅ **v2.0 In-Session Chat** — Phases 4–5 (shipped 2026-03-01)
- ✅ **v3.0 AgentOS Observability** — Phases 6–7 (shipped 2026-03-07)
- 🚧 **v4.0 Agentic Backend Refactor** — Phases 8–10 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–3) — SHIPPED 2026-02-28</summary>

- [x] Phase 1: URL Session Pipeline (8/8 plans) — completed 2026-02-19
- [x] Phase 2: Topic Description Path (4/4 plans) — completed 2026-02-28
- [x] Phase 3: Study Experience Polish (5/5 plans) — completed 2026-02-28

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v2.0 In-Session Chat (Phases 4–5) — SHIPPED 2026-03-01</summary>

- [x] Phase 4: Chat Backend (2/2 plans) — completed 2026-03-01
- [x] Phase 5: Chat Frontend (2/2 quick tasks) — completed 2026-03-01

Full details: [milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

<details>
<summary>✅ v3.0 AgentOS Observability (Phases 6–7) — SHIPPED 2026-03-07</summary>

- [x] Phase 6: AgentOS Core Integration (3/3 plans) — completed 2026-03-06
- [x] Phase 7: Control Plane Connection (2/2 plans) — completed 2026-03-07

Full details: [milestones/v3.0-ROADMAP.md](milestones/v3.0-ROADMAP.md)

</details>

### v4.0 Agentic Backend Refactor (In Progress)

**Milestone Goal:** Replace plain-Python workflow workarounds with Agno-native Workflow and Team primitives, backed by SQLite session storage so all agents share the same extracted context without the client re-sending it.

- [x] **Phase 8: Storage and Workflow Foundation** — SQLite session storage established and Agno Workflow subclass verified via SQLite round-trip (completed 2026-03-07)
- [ ] **Phase 9: Team Integration and Eager Generation** — TutorTeam coordinates generation agents; user can opt into eager generation at session creation
- [ ] **Phase 10: API Simplification** — Regenerate and chat endpoints load notes from storage; frontend stops sending notes in request bodies

## Phase Details

### Phase 8: Storage and Workflow Foundation
**Goal**: Session data persists server-side in SQLite and is readable across requests via a verified round-trip
**Depends on**: Phase 7 (v3.0 complete)
**Requirements**: STOR-01, STOR-02, STOR-03, WKFL-01, WKFL-02, WKFL-03
**Success Criteria** (what must be TRUE):
  1. After session creation completes, notes, tutoring_type, session_type, and sources are readable from SQLite by their session_id without re-sending them from the client
  2. Session data is stored in a separate SQLite file from AgentOS traces, with its path configurable via the `SESSION_DB_PATH` environment variable
  3. A request referencing an expired or unknown session_id receives a clear error response (not a silent failure or crash)
  4. `SessionWorkflow` is a proper `agno.workflow.Workflow` subclass with `run()` writing to `session_state`, and the SSE stream end-to-end is verified intact after the refactor
**Plans**: 2 plans
Plans:
- [ ] 08-01-PLAN.md — Settings + Workflow composition refactor (STOR-01, STOR-02, WKFL-01, WKFL-02)
- [ ] 08-02-PLAN.md — Router wiring + SQLite round-trip test (STOR-03, WKFL-03)

### Phase 9: Team Integration and Eager Generation
**Goal**: TutorTeam coordinates notes, flashcard, and quiz agents; users can opt in to generating all three during session creation with resilient partial-failure handling
**Depends on**: Phase 8 (storage round-trip verified)
**Requirements**: TEAM-01, TEAM-02, TEAM-03, TEAM-04
**Success Criteria** (what must be TRUE):
  1. `TutorTeam` (`agno.team.Team` in coordinate mode) orchestrates notes, flashcard, and quiz agents — observable via AgentOS traces showing team coordination
  2. A checkbox on the create page lets users opt into eager generation; when unchecked, on-demand generation behavior is unchanged
  3. When eager generation is enabled and flashcard/quiz agents fail but notes succeed, the session completes and the study page loads with notes — no full session abort
  4. Tabs for failed eager sections show the existing Generate button so the user can trigger on-demand generation; the failure is silent to the user (no error for partial failure)
**Plans**: TBD

### Phase 10: API Simplification
**Goal**: The regenerate and chat endpoints load notes from server-side storage; the client no longer sends notes in request bodies
**Depends on**: Phase 9 (TutorTeam operational and storage reads confirmed reliable)
**Requirements**: API-01, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. Submitting a regenerate request (flashcard or quiz) with no notes field in the request body succeeds — the backend loads notes from storage using session_id
  2. Submitting a chat message with no notes or tutoring_type in the request body succeeds — chat remains grounded in session material loaded from storage
  3. The frontend no longer includes notes in regenerate or chat request payloads — verified by inspecting outgoing network requests in browser devtools
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. URL Session Pipeline | v1.0 | 8/8 | Complete | 2026-02-19 |
| 2. Topic Description Path | v1.0 | 4/4 | Complete | 2026-02-28 |
| 3. Study Experience Polish | v1.0 | 5/5 | Complete | 2026-02-28 |
| 4. Chat Backend | v2.0 | 2/2 | Complete | 2026-03-01 |
| 5. Chat Frontend | v2.0 | 2/2 | Complete | 2026-03-01 |
| 6. AgentOS Core Integration | v3.0 | 3/3 | Complete | 2026-03-06 |
| 7. Control Plane Connection | v3.0 | 2/2 | Complete | 2026-03-07 |
| 8. Storage and Workflow Foundation | 2/2 | Complete   | 2026-03-07 | - |
| 9. Team Integration and Eager Generation | v4.0 | 0/TBD | Not started | - |
| 10. API Simplification | v4.0 | 0/TBD | Not started | - |
