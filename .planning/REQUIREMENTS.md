# Requirements: Super Tutor v7.0

**Defined:** 2026-03-15
**Core Value:** A user gives a topic, picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.

## v7.0 Requirements — Personal Tutor

Requirements for the Personal Tutor milestone. Continues numbering from v6.0.

### Personal Tutor Tab (TUTOR)

- [ ] **TUTOR-01**: User sees a Personal Tutor tab (4th tab) on the study page alongside Notes, Flashcards, and Quiz
- [ ] **TUTOR-02**: User can type messages to the tutor and receive streaming token-by-token responses
- [ ] **TUTOR-03**: Tutor conversation history persists across page refreshes (saved to SQLite per session_id via `tutor:{session_id}` namespace)
- [ ] **TUTOR-04**: Tutor introduces itself and its capabilities when user first opens the tab

### Agno Team Architecture (TEAM)

- [x] **TEAM-01**: Personal Tutor is backed by an Agno Team with a coordinator agent that routes to specialist sub-agents; existing agent builders (chat_agent, research_agent, notes_agent, flashcard_agent, quiz_agent) are reused as specialists — only the Coordinator and Advisor are new agents
- [x] **TEAM-02**: Coordinator interprets user intent and dispatches to the appropriate specialist without asking the user to confirm routing (silent dispatch)
- [x] **TEAM-03**: Explainer specialist (wraps existing chat_agent) answers Q&A grounded strictly in session source material and notes
- [ ] **TEAM-04**: Researcher specialist (reuses existing research_agent) extends topics via Tavily when user asks to go deeper
- [ ] **TEAM-05**: Content Writer specialist (reuses existing notes_agent, flashcard_agent, quiz_agent) generates additional notes excerpts, flashcards, or quiz questions rendered inline in chat
- [ ] **TEAM-06**: Quiz Master specialist (reuses existing quiz_agent for generation) runs in-conversation quizzes and evaluates user answers with explanation
- [ ] **TEAM-07**: Advisor specialist (new agent) surfaces focus area suggestions based on in-tutor quiz performance and conversation patterns

### Context & Inline Content (CONTENT)

- [x] **CONTENT-01**: Tutor loads existing session content at request time — source_content, notes, flashcards, and quiz questions from SQLite — as grounding context
- [ ] **CONTENT-02**: All tutor-generated content (flashcard sets, notes excerpts, quiz questions) renders inline in the tutor chat with appropriate formatting (card blocks, Q&A blocks, markdown sections); nothing is written back to the Notes, Flashcards, or Quiz tabs

### In-Tutor Quiz & Quiz Integration (QUIZ)

- [ ] **QUIZ-01**: User can ask the tutor to quiz them; Quiz Master delivers questions one at a time in-chat
- [ ] **QUIZ-02**: Tutor evaluates each answer and explains what was right or wrong before moving to the next question
- [ ] **QUIZ-03**: User can share their Quiz tab results with the tutor by describing or pasting them; tutor uses this to tailor guidance
- [ ] **QUIZ-04**: Tutor proactively asks about quiz performance when it detects the user has completed or struggled with the session quiz

### Adaptive Suggestions (ADVISE)

- [ ] **ADVISE-01**: Advisor identifies weak areas from in-tutor quiz answer patterns and topics the user asked about repeatedly
- [ ] **ADVISE-02**: Tutor proactively surfaces focus area suggestions and offers to generate targeted content inline
- [ ] **ADVISE-03**: In-tutor quiz scores and advisor-identified focus areas are persisted to SQLite per session_id

### Guardrails (GUARD)

- [ ] **GUARD-01**: Input guardrail rejects messages clearly unrelated to the session topic before coordinator dispatches; uses LLM-as-judge approach (not pattern-matching) to avoid false positives on educational phrasing
- [ ] **GUARD-02**: Output guardrail validates generated content for coherence and topic relevance before it is streamed to the user
- [x] **GUARD-03**: All specialist agents carry a system constraint grounding responses strictly to session source material; Researcher is the only agent permitted to introduce external information

## Future Requirements (v7.1+)

### Content Tab Merge (deferred)

- **MERGE-01**: Approved tutor-generated flashcards appended to the session Flashcard tab
- **MERGE-02**: Approved tutor-generated notes appended to the session Notes tab
- **MERGE-03**: Approved tutor-generated quiz questions appended to the session Quiz tab

### Rich Content Envelope (deferred — needs protocol design spike)

- **ENV-01**: SSE stream carries structured content envelopes (JSON-typed) for flashcard/quiz blocks with custom frontend rendering
- **ENV-02**: Frontend stream parser branches on content_type field to render card components vs plain text

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dynamic merge into Notes/Flashcards/Quiz tabs | High complexity, tab UIs not designed for dynamic growth, provenance confusion — all tutor content stays in-chat |
| Socratic agent as a separate specialist | Coordinator system prompt variant is sufficient; separate agent adds routing complexity |
| Voice input/output | Text-only; consistent with existing app |
| Cross-session tutor history | No accounts; history is per session_id only |
| AgentOS Teams registration | `AgentOS(teams=[])` param unverified in 2.5.8 — omit if unsupported, traces still work via `db=traces_db` |

## Traceability

All 23 v7.0 requirements mapped to phases. Updated during roadmap creation (2026-03-15).

| Requirement | Phase | Status |
|-------------|-------|--------|
| TUTOR-01 | Phase 16 | Pending |
| TUTOR-02 | Phase 14 | Pending |
| TUTOR-03 | Phase 14 | Pending |
| TUTOR-04 | Phase 16 | Pending |
| TEAM-01 | Phase 14 | Complete |
| TEAM-02 | Phase 14 | Complete |
| TEAM-03 | Phase 14 | Complete |
| TEAM-04 | Phase 15 | Pending |
| TEAM-05 | Phase 15 | Pending |
| TEAM-06 | Phase 17 | Pending |
| TEAM-07 | Phase 18 | Pending |
| CONTENT-01 | Phase 14 | Complete |
| CONTENT-02 | Phase 16 | Pending |
| QUIZ-01 | Phase 17 | Pending |
| QUIZ-02 | Phase 17 | Pending |
| QUIZ-03 | Phase 17 | Pending |
| QUIZ-04 | Phase 18 | Pending |
| ADVISE-01 | Phase 18 | Pending |
| ADVISE-02 | Phase 18 | Pending |
| ADVISE-03 | Phase 18 | Pending |
| GUARD-01 | Phase 15 | Pending |
| GUARD-02 | Phase 15 | Pending |
| GUARD-03 | Phase 14 | Complete |

**Coverage:**
- v7.0 requirements: 23 total
- Mapped to phases: 23
- Unmapped: 0

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-15 after roadmap creation — all 23 requirements mapped*
