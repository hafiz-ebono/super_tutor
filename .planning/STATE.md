# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.
**Current focus:** v2.0 In-Session Chat — Phase 4 (Chat Backend) in progress

## Current Position

Phase: 4 of 5 (Chat Backend)
Plan: 1 of ? in current phase
Status: In progress
Last activity: 2026-03-01 - Completed quick task 4: Chat UI — floating bubble and sliding pane

Progress: [████████░░] 80% (v1.0 complete, v2.0 not started)

## Performance Metrics

**Velocity:**
- Total plans completed: 17 (v1.0)
- Average duration: ~4 min
- Total execution time: ~68 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-url-session-pipeline | 8 | ~38min | ~5min |
| 02-topic-description-path | 4 | ~20min | ~5min |
| 03-study-experience-polish | 5 | ~10min | ~2min |
| 04-chat-backend | 1 | ~2min | ~2min |

**Recent Trend:**
- Last 5 plans: 03-01 (2min), 03-02 (2min), 03-03 (2min), 03-04 (2min), 03-05 (2min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [v2.0 research]: Use `fetch` + `ReadableStream` for chat POST streaming — not `EventSource` (GET-only); avoids PENDING_STORE two-step workaround
- [v2.0 research]: Send session notes as chat system context, not raw article — already compressed, lower token cost per turn
- [v2.0 research]: Cap conversation history at 6 turns sent to backend; display all turns in UI
- [v2.0 research]: `chatHistory` in component state (not localStorage) — ephemeral per page load, consistent with stateless model
- [v2.0 research]: Gate chat availability on notes being present — notes exist after SSE complete, before flashcard/quiz generation
- [Phase 03-04]: `asyncio.to_thread` used for sync `agent.run()` calls inside async generator — same pattern applies to chat agent
- [Phase 04-01]: Stateless agent per request — new Agent constructed on every request; client owns conversation history
- [Phase 04-01]: Hard grounding wording: "Answer ONLY from the session material" with explicit fallback response string
- [Phase 04-01]: List[Message] passed to agent.arun() — history + current message; last Message(role=user) is current turn per Agno 2.5.2
- [Phase 04-01]: No server-side history cap — 6-turn limit is enforced client-side

### Pending Todos

None yet.

### Blockers/Concerns

None identified for v2.0 phases.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 2 | Migrate research agent from DuckDuckGo to Tavily for web search | 2026-02-28 | e7f7b33 | [2-migrate-research-agent-from-duckduckgo-t](./quick/2-migrate-research-agent-from-duckduckgo-t/) |
| 3 | Title agent error fallback to user input (topic_description or URL) | 2026-03-01 | a5c670f | [3-title-agent-error-fallback-to-user-input](./quick/3-title-agent-error-fallback-to-user-input/) |
| 4 | Chat UI — floating bubble and sliding pane with SSE streaming | 2026-03-01 | 3f721e3 | [4-chat-ui-floating-bubble-and-sliding-pane](./quick/4-chat-ui-floating-bubble-and-sliding-pane/) |

## Session Continuity

Last session: 2026-03-01
Stopped at: Completed quick-4 (chat UI — floating bubble and sliding pane with SSE streaming)
Resume file: None
