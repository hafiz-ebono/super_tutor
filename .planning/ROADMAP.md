# Roadmap: Super Tutor

## Milestones

- ✅ **v1.0 MVP** - Phases 1-3 (shipped 2026-02-28)
- ✅ **v2.0 In-Session Chat** - Phases 4-5 (shipped 2026-03-01)
- ✅ **v3.0 AgentOS Observability** - Phases 6-7 (shipped 2026-03-07)
- ✅ **v4.0 Agentic Backend Refactor** - Phase 8 (shipped 2026-03-12)
- ✅ **v5.0 API Simplification** - Phases 9-10 (shipped 2026-03-13)
- ✅ **v6.0 Document Upload** - Phases 11-13 (shipped 2026-03-14)
- 🚧 **v7.0 Personal Tutor** - Phases 14-18 (in progress)

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

<details>
<summary>✅ v6.0 Document Upload (Phases 11-13) — SHIPPED 2026-03-14</summary>

- [x] Phase 11: Backend Foundation (3/3 plans) — completed 2026-03-13
- [x] Phase 12: Backend Upload Endpoint (3/3 plans) — completed 2026-03-14
- [x] Phase 13: Frontend Upload UI (4/4 plans) — completed 2026-03-14

</details>

### 🚧 v7.0 Personal Tutor (In Progress)

**Milestone Goal:** Transform the study page into an adaptive tutoring experience — a persistent, session-grounded Agno Team that answers questions, runs quizzes, generates inline content, and surfaces focus area suggestions.

- [ ] **Phase 14: Team Foundation** - Coordinator + Explainer with streaming, persistence validation, and session grounding
- [ ] **Phase 15: Full Specialist Roster + Guardrails** - Researcher, Content Writer, and topic relevance guardrails
- [ ] **Phase 16: Frontend Tutor Tab** - 4th study tab with persistent chat, history restore, and intro message
- [ ] **Phase 17: In-Tutor Quiz Mode** - In-chat MCQ delivery, answer evaluation, and quiz result integration
- [ ] **Phase 18: Adaptive Intelligence** - Advisor agent, proactive focus suggestions, and adaptive persistence

## Phase Details

### Phase 14: Team Foundation
**Goal**: A working `POST /tutor/{session_id}/stream` SSE endpoint backed by an Agno Team factory — coordinator + Explainer specialist — with confirmed async persistence and per-session namespace isolation
**Depends on**: Phase 13 (v6.0 complete — existing SSE patterns, traces_db, session storage all in place)
**Requirements**: TUTOR-02, TUTOR-03, TEAM-01, TEAM-02, TEAM-03, CONTENT-01, GUARD-03
**Success Criteria** (what must be TRUE):
  1. `POST /tutor/{session_id}/stream` returns a streaming SSE response with coordinator-routed tokens for a test message
  2. After two tutor turns, a second request's coordinator context contains the first turn's messages — confirming SQLite persistence via `tutor:{session_id}` namespace
  3. Tutor responses are strictly grounded in the session's source_content and notes loaded from SQLite — general-knowledge answers are rejected at the system prompt level
  4. The coordinator dispatches to the Explainer without asking the user to confirm routing (silent dispatch)
  5. Two concurrent requests for different session_ids do not share state — per-request factory isolation confirmed
**Plans**: 2 plans

Plans:
- [ ] 14-01-PLAN.md — Team factory (build_tutor_team), TutorStreamRequest model, tutor_history_window config
- [ ] 14-02-PLAN.md — POST /tutor/{session_id}/stream SSE router and main.py registration

### Phase 15: Full Specialist Roster + Guardrails
**Goal**: All specialist agents (Researcher, Content Writer) wired into the Team, and topic relevance guardrails calibrated against realistic tutor traffic
**Depends on**: Phase 14
**Requirements**: TEAM-04, TEAM-05, GUARD-01, GUARD-02
**Success Criteria** (what must be TRUE):
  1. When a user asks to "go deeper" on a topic, the coordinator routes to Researcher and the response includes Tavily-sourced external information
  2. When a user asks for extra flashcards or a notes excerpt, the coordinator routes to Content Writer and the output renders as generated inline content
  3. Off-topic messages (e.g., "write me a poem about dogs") are rejected with a polite redirect before coordinator dispatch — no specialist is invoked
  4. Educational phrasing ("pretend you're a teacher", "ignore what I said") does not trigger a false-positive rejection — LLM-as-judge distinguishes intent correctly
**Plans**: TBD

Plans:
- [ ] 15-01: TBD

### Phase 16: Frontend Tutor Tab
**Goal**: Users see a Personal Tutor tab as the 4th study tab; opening it restores persisted conversation history and displays a tutor introduction
**Depends on**: Phase 14 (streaming endpoint curl-verified), Phase 15 (guardrails in place)
**Requirements**: TUTOR-01, TUTOR-04, CONTENT-02
**Success Criteria** (what must be TRUE):
  1. A "Personal Tutor" tab appears alongside Notes, Flashcards, and Quiz on the study page
  2. When the user opens the Tutor tab for the first time, the tutor sends an introduction message describing its capabilities
  3. After a page refresh, opening the Tutor tab restores all prior conversation messages without the user having to re-send anything
  4. Tutor-generated flashcard sets, notes excerpts, and quiz questions render inline in the chat with distinct formatting — nothing is written to the Notes, Flashcards, or Quiz tabs
**Plans**: TBD

Plans:
- [ ] 16-01: TBD

### Phase 17: In-Tutor Quiz Mode
**Goal**: Users can ask the tutor to quiz them; Quiz Master delivers one MCQ at a time, evaluates answers, and accepts shared Quiz tab results as context
**Depends on**: Phase 15 (full specialist roster), Phase 16 (frontend tab stable)
**Requirements**: QUIZ-01, QUIZ-02, QUIZ-03, TEAM-06
**Success Criteria** (what must be TRUE):
  1. When a user says "quiz me", the tutor delivers a multiple-choice question inline in the chat with selectable answer options
  2. After the user selects an answer, the tutor evaluates it and explains what was right or wrong before delivering the next question
  3. When a user shares or describes their Quiz tab results in the tutor chat, the tutor acknowledges the result and adjusts its guidance accordingly
**Plans**: TBD

Plans:
- [ ] 17-01: TBD

### Phase 18: Adaptive Intelligence
**Goal**: The Advisor identifies weak areas from quiz patterns and conversation history, surfaces proactive focus suggestions, and persists adaptive data to SQLite
**Depends on**: Phase 17 (in-tutor quiz mode complete — Advisor needs quiz score signals)
**Requirements**: TEAM-07, QUIZ-04, ADVISE-01, ADVISE-02, ADVISE-03
**Success Criteria** (what must be TRUE):
  1. After a user completes an in-tutor quiz, the tutor proactively asks about quiz performance if it detects the user struggled
  2. The Advisor identifies concepts the user asked about repeatedly or answered incorrectly, and surfaces them as named focus areas in the conversation
  3. When focus areas are identified, the tutor offers to generate targeted inline content (additional flashcards or a mini-quiz on the weak concept)
  4. In-tutor quiz scores and identified focus areas survive a page refresh — they are persisted to SQLite per session_id and reload with conversation history
**Plans**: TBD

Plans:
- [ ] 18-01: TBD

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
| 13. Frontend Upload UI | v6.0 | 4/4 | Complete | 2026-03-14 |
| 14. Team Foundation | 1/2 | In Progress|  | - |
| 15. Full Specialist Roster + Guardrails | v7.0 | 0/TBD | Not started | - |
| 16. Frontend Tutor Tab | v7.0 | 0/TBD | Not started | - |
| 17. In-Tutor Quiz Mode | v7.0 | 0/TBD | Not started | - |
| 18. Adaptive Intelligence | v7.0 | 0/TBD | Not started | - |
