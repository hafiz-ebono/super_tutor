# Requirements: Super Tutor

**Defined:** 2026-02-28
**Milestone:** v2.0 In-Session Chat
**Core Value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v2.0 Requirements

### Chat — Core Interaction

- [ ] **CHAT-01**: User can open a floating chat panel from any tab on the study page
- [ ] **CHAT-02**: User can close the chat panel without losing conversation history
- [ ] **CHAT-03**: User can type and submit a message to the AI
- [x] **CHAT-04**: AI response streams word by word (not delivered all at once)
- [x] **CHAT-05**: AI responses are grounded in the session notes (not general knowledge)
- [x] **CHAT-06**: Chat adapts tone to the session's tutoring mode (Micro / Kid / Advanced)

### Chat — Conversation Experience

- [x] **CHAT-07**: Chat maintains multi-turn conversation history (AI remembers earlier messages in the session)
- [ ] **CHAT-08**: User can scroll through previous messages in the chat panel
- [ ] **CHAT-09**: Chat history resets when the user leaves or refreshes the page (ephemeral — consistent with app's stateless model)

## Future Requirements

*(None identified — v2.0 is focused on chat MVP)*

## Out of Scope

| Feature | Reason |
|---------|--------|
| Persistent chat history across sessions | Requires user accounts; out of scope for v2 |
| Proactive AI (Socratic questioning) | User chose free chat model — AI responds, doesn't initiate |
| Chat export or copy | Not a launch requirement; low frequency action |
| File/image upload in chat | Text-only session material; no need for multimodal chat input |
| Suggested starter questions | Nice-to-have; deferred to post-launch polish |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CHAT-01 | Phase 5 | Pending |
| CHAT-02 | Phase 5 | Pending |
| CHAT-03 | Phase 5 | Pending |
| CHAT-04 | Phase 4 | Complete |
| CHAT-05 | Phase 4 | Complete |
| CHAT-06 | Phase 4 | Complete |
| CHAT-07 | Phase 4 | Complete |
| CHAT-08 | Phase 5 | Pending |
| CHAT-09 | Phase 5 | Pending |

**Coverage:**
- v2.0 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-02-28*
*Last updated: 2026-02-28 — traceability confirmed after roadmap creation*
