# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-18)

**Core value:** A user gives a topic (URL or description), picks how they want to learn, and gets a complete, ready-to-study session in minutes — no account needed, no friction.
**Current focus:** Phase 1 — URL Session Pipeline

## Current Position

Phase: 1 of 3 (URL Session Pipeline)
Plan: 7 of 8 in current phase
Status: In progress
Last activity: 2026-02-19 — Plan 07 complete: Loading page (SSE consumer) and study page (sidebar, notes, flashcards, quiz)

Progress: [█████████░] 87%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 4min
- Total execution time: 28min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-url-session-pipeline | 7 | 28min | 4min |

**Recent Trend:**
- Last 5 plans: 01-02 (4min), 01-03 (3min), 01-04 (3min), 01-05 (5min), 01-07 (4min)
- Trend: Stable

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Pre-phase]: Agno framework required for all AI agents (AGENT-01) — must be addressed in Phase 1 alongside first agent work, not retrofitted later
- [Pre-phase]: Chat deferred to v2 (CHAT-01, CHAT-02) — removes SSE chat infrastructure from v1 scope
- [Pre-phase]: Topic description path (SESS-02) deferred to Phase 2 — URL path proves the generation pipeline first
- [Pre-phase]: URL extraction chain: Jina Reader → trafilatura → Playwright → paste-text fallback — verify Jina pricing before Phase 1 implementation
- [01-01]: Lazy imports inside get_model() branches — provider SDK only imported when selected, avoiding ImportError if optional packages absent
- [01-01]: lru_cache on get_settings() — single Settings instance per process, avoiding repeated .env reads
- [01-01]: PERSONAS stored as plain dict[str, str] — system prompts editable without touching agent code
- [01-02]: OAT UI CDN URL is https://oat.ink/oat.min.css (plan had oat.css which 404s; confirmed oat.min.css returns 200)
- [01-02]: No oat-ui npm package exists; CDN link in root layout <head> is the integration approach
- [01-02]: .env.local is gitignored by Next.js defaults; NEXT_PUBLIC_API_URL must be created manually
- [01-05]: Two-step SSE flow required — POST stores params, GET /stream runs pipeline (EventSource is GET-only)
- [01-05]: asyncio.sleep(0) between workflow steps ensures SSE frame flushing step-by-step not buffered
- [01-05]: sse-starlette 3.2.0 requires fastapi>=0.115.0; upgraded from 0.104.1 to 0.129.0 to fix middleware stack ValueError
- [Phase 01-07]: useState<string> explicit type annotation needed when initializing from as-const array element — avoids literal type inference blocking string setters
- [Phase 01-07]: 400ms delay after SSE complete event lets user see 100% progress bar before router.push redirect

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 1 pre-work]: Jina AI Reader pricing and rate limits unconfirmed — verify before building the URL extraction chain (research flags this as MEDIUM confidence)
- [Phase 2 pre-work]: Tavily pricing and rate limits unconfirmed — verify before Phase 2 planning
- [01-01 resolved]: Tutoring mode persona specifications — written and committed in personas.py (micro_learning, teaching_a_kid, advanced)

## Session Continuity

Last session: 2026-02-19
Stopped at: Completed 01-07-PLAN.md — Loading page (SSE consumer) and study page (sidebar, notes, flashcards, quiz)
Resume file: None
