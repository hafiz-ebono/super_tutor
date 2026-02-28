---
phase: quick-4
plan: "01"
subsystem: frontend
tags: [chat, ui, streaming, sse, sliding-panel, floating-bubble]
dependency_graph:
  requires: [Phase 04-01 — /chat/stream backend endpoint]
  provides: [In-session chat UI — floating bubble + sliding panel + SSE streaming]
  affects: [frontend/src/app/study/[sessionId]/page.tsx]
tech_stack:
  added: []
  patterns:
    - fetch POST + ReadableStream for SSE streaming (not EventSource)
    - Optimistic UI: user message appended before server response
    - Token-by-token streaming: setChatHistory functional update per token
    - History cap enforced client-side: history.slice(0, -1).slice(-6)
key_files:
  created: []
  modified:
    - frontend/src/app/study/[sessionId]/page.tsx
decisions:
  - "Bubble z-[60] above panel z-[55] so toggle icon stays on top"
  - "Panel style top:56px aligns below app header on both mobile and desktop"
  - "history.slice(0, -1).slice(-6) correctly excludes current message and caps at 6 prior turns"
  - "chatHistory is component state only — ephemeral per page load, no localStorage"
metrics:
  duration: "~6 min"
  completed: "2026-03-01"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 1
---

# Quick Task 4: Chat UI — Floating Bubble and Sliding Panel Summary

**One-liner:** In-session chat with floating bubble, CSS slide-in panel, and live SSE token streaming backed by `/chat/stream`.

## What Was Built

Added a complete in-session chat feature to the study page, allowing users to ask questions about session content without leaving the page. The chat is grounded in `session.notes` and uses the stateless `/chat/stream` backend endpoint.

### Task 1: Chat State + sendMessage Streaming Function

Added four state variables to the `StudyPage` component:
- `chatOpen` — panel open/closed toggle
- `chatHistory` — array of `{ role: "user" | "assistant"; content: string }` messages (ephemeral)
- `chatInput` — controlled textarea value
- `isStreaming` — disables input/send while stream is in progress

Added `sendMessage` async function:
- Optimistically appends user message then empty assistant placeholder
- POSTs to `/chat/stream` with `message`, `notes`, `tutoring_type`, and `history` (capped at 6 prior turns via `history.slice(0, -1).slice(-6)`)
- Reads SSE stream via `ReadableStream` reader with line-buffer accumulator
- Parses `data: {"token": "..."}` lines and appends tokens to the last assistant message via functional `setChatHistory`
- On error: replaces empty placeholder with fallback error string
- `finally`: always clears `isStreaming`

### Task 2: Floating Bubble + Sliding Panel JSX

**Main content shift:** `<main>` tag gets `md:mr-[360px]` class when `chatOpen` is true, pushing desktop content left to avoid overlap with the 360px wide panel. Uses `transition-all duration-300` for smooth animation.

**Floating bubble:** Fixed position, `bottom-20 right-4` on mobile (above the 56px tab bar), `md:bottom-6 md:right-6` on desktop. `z-[60]`. Shows chat icon when closed, X icon when open. Only renders when `session && session.notes`.

**Sliding panel:** Fixed position, `top: 56px` (below app header), full width on mobile, `md:w-[360px]` on desktop. `z-[55]`. Slides in/out via `translate-x-0` / `translate-x-full` CSS transition.

Panel sections:
- **Header:** "Ask about this session" title + close button
- **Message list:** Scrollable flex column. Empty state shows hint text. User messages right-aligned in blue bubble, assistant messages left-aligned in zinc-100 bubble. Empty assistant content shows 3-dot bounce animation (streaming indicator).
- **Input area:** Auto-resize textarea (max-height 120px), Enter (without Shift) triggers send, send button with arrow icon. Both disabled while `isStreaming`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

### Files Verified

- `frontend/src/app/study/[sessionId]/page.tsx` — modified, exists

### Commits Verified

- `3da535d` — feat(quick-4-01): add chat state and sendMessage SSE streaming function
- `3f721e3` — feat(quick-4-02): add floating chat bubble and sliding chat panel to study page

### Build Verified

- TypeScript: zero errors (`npx tsc --noEmit`)
- Next.js build: compiled successfully, all routes generated

## Self-Check: PASSED
