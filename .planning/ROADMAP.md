# Roadmap: Super Tutor

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3 (shipped 2026-02-28)
- ✅ **v2.0 In-Session Chat** — Phases 4–5 (shipped 2026-03-01)
- 🔄 **v3.0 AgentOS Observability** — Phases 6–7 (in progress)

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

### v3.0 AgentOS Observability

- [ ] **Phase 6: AgentOS Core Integration** — Wrap FastAPI with AgentOS, wire all agents with db=, stand up SQLite trace storage, and validate full local tracing
- [ ] **Phase 7: Control Plane Connection** — Connect the backend to app.agno.com and verify agent runs, costs, and session data are visible in the Control Plane

## Phase Details

### Phase 6: AgentOS Core Integration
**Goal**: All agents produce structured traces stored in local SQLite — token usage, latency, errors, and session isolation all captured, with AgentOS wrapping the existing FastAPI app without breaking any SSE endpoints
**Depends on**: Nothing (first phase of this milestone; builds on shipped v2.0 backend)
**Requirements**: INT-01, INT-02, INT-03, TRAC-01, TRAC-02, TRAC-03, TRAC-04, STOR-01, STOR-02
**Success Criteria** (what must be TRUE):
  1. The FastAPI app starts under AgentOS (`base_app=app`) and all existing SSE endpoints (`/session/stream`, `/chat/stream`, `/generate/*`) respond correctly
  2. Every agent run (notes, chat, research, flashcard, quiz) creates a trace row in the SQLite file with inputs, outputs, and latency
  3. Each trace row includes LLM token usage (input tokens, output tokens) and the model name used
  4. A tenacity retry event (e.g. triggered by a 429) produces a visible error/retry entry in the trace rather than disappearing silently
  5. Running two overlapping sessions produces trace rows scoped to their own session identifiers — no cross-session bleed when querying the db
**Plans**: TBD

### Phase 7: Control Plane Connection
**Goal**: The running backend is connected to AgentOS Control Plane at app.agno.com so agent runs, token costs, and session data are remotely visible without any local database queries
**Depends on**: Phase 6
**Requirements**: CTRL-01, CTRL-02, CTRL-03
**Success Criteria** (what must be TRUE):
  1. The backend authenticates to app.agno.com on startup (AGNO_API_KEY env var set; no manual step required)
  2. After triggering a session or chat turn, the corresponding agent run appears in the Control Plane trace explorer within a few seconds
  3. The Control Plane UI shows session-level cost (token spend) and can be filtered or queried by session
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. URL Session Pipeline | v1.0 | 8/8 | Complete | 2026-02-19 |
| 2. Topic Description Path | v1.0 | 4/4 | Complete | 2026-02-28 |
| 3. Study Experience Polish | v1.0 | 5/5 | Complete | 2026-02-28 |
| 4. Chat Backend | v2.0 | 2/2 | Complete | 2026-03-01 |
| 5. Chat Frontend | v2.0 | 2/2 | Complete | 2026-03-01 |
| 6. AgentOS Core Integration | v3.0 | 0/? | Not started | - |
| 7. Control Plane Connection | v3.0 | 0/? | Not started | - |
