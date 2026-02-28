# Roadmap: Super Tutor

## Milestones

- ✅ **v1.0 MVP** — Phases 1–3 (shipped 2026-02-28)
- 🚧 **v2.0 In-Session Chat** — Phases 4–5 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–3) — SHIPPED 2026-02-28</summary>

- [x] Phase 1: URL Session Pipeline (8/8 plans) — completed 2026-02-19
- [x] Phase 2: Topic Description Path (4/4 plans) — completed 2026-02-28
- [x] Phase 3: Study Experience Polish (5/5 plans) — completed 2026-02-28

Full details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### 🚧 v2.0 In-Session Chat (In Progress)

**Milestone Goal:** Let users have a streaming, multi-turn AI conversation about their session content directly from the study page — grounded in notes, ephemeral per session, no account required.

- [ ] **Phase 4: Chat Backend** - Streaming `/chat/stream` endpoint with Agno chat agent, notes-grounded system prompt, and history-capped multi-turn context
- [ ] **Phase 5: Chat Frontend** - Floating chat bubble, sliding side panel, fetch+ReadableStream SSE client, and ephemeral history display

## Phase Details

### Phase 4: Chat Backend
**Goal**: The backend can accept a message, session notes, tutoring type, and conversation history, then stream a grounded AI response token by token
**Depends on**: Phase 3 (v1.0 complete)
**Requirements**: CHAT-04, CHAT-05, CHAT-06, CHAT-07
**Success Criteria** (what must be TRUE):
  1. A POST to `/chat/stream` with a message and session notes returns a streaming SSE response where tokens arrive word by word, not all at once
  2. The AI only answers from the session notes — asking about something not in the notes yields a "I can only answer about this session's material" response, not a general answer
  3. The AI tone matches the tutoring type — the same question gets a different register when `tutor_type` is Micro vs Advanced
  4. Sending the last 6 turns of conversation history causes the AI to reference earlier messages correctly, demonstrating multi-turn memory within a request
**Plans**: 2 plans

Plans:
- [ ] 04-01-PLAN.md — Pydantic request model (ChatStreamRequest) + Agno chat agent builder (build_chat_agent, build_chat_messages)
- [ ] 04-02-PLAN.md — POST /chat/stream router with SSE streaming + main.py wiring + end-to-end verification checkpoint

### Phase 5: Chat Frontend
**Goal**: Users can open a floating chat panel from any tab on the study page, send messages, watch responses stream in, scroll through history, and close the panel without losing conversation context
**Depends on**: Phase 4
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-08, CHAT-09
**Success Criteria** (what must be TRUE):
  1. A floating chat bubble is visible on the study page regardless of which tab (Notes, Flashcards, Quiz) is active
  2. Clicking the bubble opens a side panel that slides in without hiding the study content underneath; clicking close slides the panel out
  3. Closing and reopening the chat panel shows the same conversation history — no messages lost from closing the panel
  4. User types a message, submits, and sees the AI response appear token by token in the panel as it streams
  5. After several messages, the user can scroll upward in the panel to read earlier turns; navigating away or refreshing the page resets history to empty
**Plans**: TBD

Plans:
- [ ] 05-01: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. URL Session Pipeline | v1.0 | 8/8 | Complete | 2026-02-19 |
| 2. Topic Description Path | v1.0 | 4/4 | Complete | 2026-02-28 |
| 3. Study Experience Polish | v1.0 | 5/5 | Complete | 2026-02-28 |
| 4. Chat Backend | 1/2 | In Progress|  | - |
| 5. Chat Frontend | v2.0 | 0/? | Not started | - |
