# Project Research Summary

**Project:** Super Tutor
**Domain:** AI Tutoring / LLM-Powered Ed-Tech Web App
**Researched:** 2026-02-18
**Confidence:** MEDIUM

## Executive Summary

Super Tutor is an ephemeral, single-session AI tutoring web app that transforms a URL or topic description into structured study materials (notes, flashcards, quiz) and an in-session AI chat grounded in that content. The recommended build approach is a stateless FastAPI backend that ingests content, runs three parallel LLM generation calls, returns the complete session payload to the frontend, and then stays out of the way. The frontend owns all session state for its lifetime. This design eliminates database, auth, and session management complexity for v1, and scales trivially to concurrent users. The OAT UI frontend and FastAPI backend are pre-decided constraints; all other stack decisions follow from those anchors.

The core competitive differentiation is the combination of URL-plus-focus-prompt ingestion, three genuinely distinct tutoring modes (Micro / Kid / Advanced), and zero-friction ephemeral sessions with no account required. No major competitor (Khanmigo, Quizlet Q-Chat, StudyFetch) offers all three simultaneously as of mid-2025. The topic description input path (AI-researched content) is a secondary differentiator that significantly expands the addressable use case to "I want to learn X from scratch," but it is architecturally more complex than the URL path and carries higher hallucination risk — it should be built after the URL path is validated.

The two risks that would most directly undermine the product's credibility are (1) confident hallucination in educational content and (2) web scraping brittleness causing silent bad generations. Both must be addressed in Phase 1, not deferred. A third risk — users abandoning sessions due to silent generation waits of 30-90 seconds — is a launch-blocking UX requirement, not an optional optimization.

---

## Key Findings

### Recommended Stack

The backend is Python 3.12 + FastAPI (^0.115) + Pydantic v2 (^2.9) + Uvicorn. LLM calls go through the `openai` SDK (^1.57) with the `anthropic` SDK (^0.40) available as a swap-in. Model split: GPT-4o for session generation (reliable structured JSON output), GPT-4o-mini for in-session chat (faster, cheaper for conversational turns). The explicit recommendation against LangChain and LlamaIndex is strong — this project has no vector pipeline and the abstraction overhead is not justified.

URL content extraction uses a layered chain: Jina AI Reader (managed service, handles JS-rendered pages, returns clean markdown) → trafilatura (^2.0, DIY fallback article extractor) → Playwright (^1.49, headless browser last resort) → error with paste-text fallback offered to user. Web research for the topic path uses Tavily (`tavily-python ^0.5`), which combines search and content extraction in one call. The in-session RAG chat uses context-stuffing only — session content is 1,000–4,000 tokens, well within GPT-4o's 128k window. No vector database is needed or appropriate in v1.

**Core technologies:**
- `fastapi ^0.115`: Async web framework with native SSE support via `StreamingResponse` — required for streaming chat and generation progress
- `openai ^1.57` + `anthropic ^0.40`: Primary and fallback LLM SDKs — thin `llm_client.py` wrapper decouples the rest of the codebase from SDK-specific signatures
- `pydantic ^2.9`: Validation and structured LLM output parsing — required for reliable flashcard and quiz JSON schemas
- `httpx ^0.28`: Async HTTP client for URL fetching — replaces synchronous `requests` which would block the event loop
- Jina AI Reader via `httpx GET r.jina.ai/{url}`: Managed URL extraction — handles the 40-60% of real URLs that simple BeautifulSoup scraping fails on
- `trafilatura ^2.0`: Article extraction fallback — purpose-built for boilerplate removal, better than raw BeautifulSoup
- `tavily-python ^0.5`: Web research for topic path — search plus content extraction in one call, designed for LLM pipelines
- `marked ^15.0` + `dompurify ^3.2`: Frontend markdown rendering and XSS sanitisation — required before any `innerHTML` injection of LLM output

### Expected Features

The market research confirms that users of any AI study tool arrive with the following baseline expectations baked in:

**Must have (table stakes):**
- Content ingestion (URL or text paste) — feels broken without it; plain-text fallback is critical for paywall/scraping failure recovery
- Structured notes generation — the primary output; quality here determines whether users trust the product
- Flashcard generation — spaced repetition is the dominant study technique; expected from any study app
- Multiple-choice quiz with automatic grading — completes the active recall loop; multiple choice is reliable to generate and grade without complex rubric logic
- In-session AI chat grounded in session content — post-ChatGPT baseline expectation; the "grounded" part is what makes it useful rather than just another chatbot
- Progress/streaming feedback during generation — users abandon after 10 seconds of silence; this is a launch requirement, not a feature
- Responsive single-page session view — dense walls of text and page fragmentation kill engagement
- Graceful error handling for bad inputs — paywalled URLs, broken links, vague topics; this is where ed-tech apps repeatedly fail users

**Should have (competitive):**
- Tutoring type / tone adaptation (Micro / Kid / Advanced) — genuinely rare; no major competitor has this as a first-class feature
- URL + focus prompt combination — letting users scope which aspect of a URL to study is differentiated and technically simple
- Deep topic research mode (AI-researched, no URL required) — expands use cases significantly; higher complexity and hallucination risk
- Zero-friction ephemeral sessions (no account required) — eliminates the #1 drop-off point in ed-tech onboarding
- Flashcard flip interaction with keyboard navigation — outsized perceived quality impact for low implementation cost
- Quiz answer explanations (why correct answer is right) — ties learning back to source material; add after quiz generation quality is validated

**Defer (v2+):**
- User accounts and authentication — 2-4 weeks of infrastructure work, GDPR considerations, and onboarding friction; defer until there is validated demand for returning users
- Spaced repetition scheduling (Anki-style) — requires accounts and scheduling logic; cannot exist without persistence
- Video / YouTube URL ingestion — separate transcription pipeline; Whisper integration changes the content extraction architecture significantly
- Export to PDF / Anki / Notion — power-user feature, low frequency; add copy-to-clipboard first
- Gamification (streaks, XP, badges) — meaningless without persistence; risks distracting from core content quality work
- Shareable session links (ephemeral, TTL-based) — requires Redis; add in v1.x when users start asking "how do I share this?"

### Architecture Approach

The architecture is a stateless backend / stateful frontend split. FastAPI ingests content (URL or topic), runs notes + flashcards + quiz generation in parallel via `asyncio.gather`, and returns the full session payload in a single HTTP response. The frontend (OAT UI / TypeScript) owns all session state in `sessionStorage` or a module-level variable for the browser session's lifetime. The backend is completely stateless between requests — it holds no session data. In-session RAG chat uses context-stuffing: the frontend sends `{message, session_content, chat_history, tutor_type}` on every chat turn; the backend builds the full prompt and streams tokens back via SSE. No vector database, no embedding pipeline, no server-side session store.

**Major components:**
1. Content Ingestion (URL path) — httpx fetch → Jina Reader → trafilatura fallback → Playwright fallback → content validation → token-budget truncation
2. Content Ingestion (Topic path) — Tavily web search → multi-source synthesis → hallucination grounding → token-budget truncation
3. Prompt Builder — centralised `prompt_builder.py`; single source of truth for all three tutoring mode specifications; generates prompts for notes, flashcards, and quiz per mode
4. LLM Orchestration — `asyncio.gather(generate_notes, generate_flashcards, generate_quiz)`; parallel calls to GPT-4o; Pydantic validation on JSON outputs; retry on parse failure
5. RAG Chat Handler — `/chat` SSE endpoint; receives full session context + history from frontend; builds system prompt with tutor mode instructions + session content; streams tokens
6. Frontend Session State — `state/session.ts`; single module holding `{raw_content, tutor_type, notes, flashcards[], quiz[], chat_history[]}`; no prop-drilling; components read directly
7. Study Page (tabs: Notes / Flashcards / Quiz) — tabbed single-page view; completion tracking in browser state only
8. Chat Panel — SSE client; scroll-locked message list; history appended client-side and round-tripped on each chat request

### Critical Pitfalls

The research identifies 7 critical pitfalls. The top 5 most likely to kill the product or require expensive retrofit:

1. **Confident hallucination in educational content** — Ground all generation in source material via system prompt ("only generate claims directly supported by the provided content"); add explicit UI disclaimer for topic-description mode; do not ask the model to "fill gaps." This is load-bearing for credibility — address in Phase 1, do not defer.

2. **Web scraping brittleness treated as solved** — Simple `requests` + BeautifulSoup works on ~40-60% of real URLs; JS-rendered pages, paywalls, and bot-protection fail silently and produce garbage generation. Use the extraction chain (Jina → trafilatura → Playwright) and always validate extracted content length before passing to the LLM. Offer paste-text fallback on failure. Address before any user testing with real URLs.

3. **No streaming / no progress feedback during generation** — Session creation takes 30-90 seconds; silent waits cause users to refresh, destroying the ephemeral session. Use SSE streaming for chat; use multi-step progress events for generation (at minimum: "Extracting content... Generating notes... Creating flashcards... Building quiz..."). This is a launch-blocking UX requirement.

4. **In-session chat losing context or answering outside session material** — Naively concatenating full article + full chat history exceeds context limits quickly; absent constraints let the model become a general chatbot. Use compressed notes (not raw article) as chat system context; cap history at last 6-10 turns; add explicit system prompt constraint: "Only answer based on session material." Design the chat context strategy before first implementation — retrofitting is expensive.

5. **Tutoring mode having no real effect on output** — Passing a label ("tutoring a child") without specifying vocabulary, analogy policy, sentence length, note structure, and question type produces superficially different but substantively identical output. Define each mode as a detailed persona spec in `prompt_builder.py` before writing any generation prompt. Side-by-side comparison across modes on the same input is the validation test.

---

## Implications for Roadmap

Based on the combined research, the feature dependencies, the architecture build order, and the pitfall-to-phase mapping, the following phase structure is recommended:

### Phase 1: Foundation and URL Session Pipeline

**Rationale:** The URL input path is the simpler of the two ingestion paths, has the most certain validation pattern, and exercises the entire generation pipeline end-to-end. Building this first proves the core loop (ingest → generate → display) before introducing the more complex topic research path. All critical pitfalls (hallucination, scraping brittleness, context overflow, tutoring mode differentiation, quiz quality) must be addressed here — they cannot be deferred without building on a broken foundation.

**Delivers:** A working session where a user submits a URL + focus prompt + tutor type, waits with visible progress feedback, and arrives at a tabbed study page with notes, flashcards, and quiz.

**Features from FEATURES.md:**
- URL input + focus prompt (P1)
- Tutoring type selection — Micro / Kid / Advanced (P1)
- Structured notes generation (P1)
- Flashcard generation (P1)
- Multiple-choice quiz generation (P1)
- Tabbed single-page session view (P1)
- Generation progress/streaming feedback (P1)
- In-session completion tracking (flashcards, quiz) (P1)
- Graceful error handling for bad URLs (paywall, empty, invalid)

**Architecture components built:**
- `llm_client.py` — thin LLM SDK wrapper
- `text_cleaner.py` — normalization and token-budget truncation
- `url_ingestion.py` — full extraction chain (Jina → trafilatura → Playwright → fallback)
- `prompt_builder.py` — centralized tutor mode specifications
- `notes.py`, `flashcards.py`, `quiz.py` — generation services with Pydantic validation
- `POST /sessions` router — wires ingestion → parallel generation → response
- Frontend: Session Form, Study Page shell, Notes / Flashcards / Quiz components
- Frontend: `state/session.ts` — session state module

**Pitfalls to avoid:**
- Hallucination (grounding prompts from day one)
- Scraping brittleness (full extraction chain, content validation gate)
- Context window overflow (token counting before LLM calls, hard ceiling)
- Tutoring mode superficiality (detailed persona specs before writing prompts)
- Trivial quiz questions (Bloom's taxonomy targeting in quiz prompt, human review)
- SSRF via user-supplied URLs (scheme validation, private IP block)
- Prompt injection via focus prompt (delimiter wrapping, sanitisation)

**Research flag:** NEEDS research-phase — URL extraction chain (Jina Reader API pricing/rate limits, trafilatura behavior on specific URL types) and prompt engineering for tutoring modes should be detailed before implementation sprint.

---

### Phase 2: In-Session AI Chat

**Rationale:** Chat is architecturally independent of the generation pipeline, but it requires the generation output to exist (notes, flashcards, quiz) before it is useful. Building it after Phase 1 validates the generation outputs also means chat's context-stuffing approach can be tested against real session payloads. Chat introduces the SSE streaming infrastructure on the backend and the EventSource / ReadableStream client on the frontend.

**Delivers:** A working chat panel where users can ask follow-up questions, get streaming responses grounded in their session content, with history managed client-side.

**Features from FEATURES.md:**
- In-session AI chat (P1)
- Streaming responses (already a P1 requirement; this phase delivers it for chat)

**Architecture components built:**
- `chat_service.py` — prompt construction (tutor mode + compressed notes as system context + capped history)
- `POST /chat` SSE endpoint — `StreamingResponse` with correct MIME type and no-cache headers
- Frontend: Chat Panel — SSE client, history management, scroll-lock

**Pitfalls to avoid:**
- Chat context drift (use compressed notes, not raw article; cap history at 6-10 turns)
- Chat answering outside session material (explicit system prompt constraint)
- SSE misconfiguration (Content-Type: text/event-stream, X-Accel-Buffering: no)
- Rate limiting absent on chat endpoint (implement per-IP limits)

**Research flag:** Standard patterns — SSE in FastAPI is well-documented; context-stuffing RAG is established; no deeper research needed before implementation.

---

### Phase 3: Topic Description Input Path (AI-Researched)

**Rationale:** The topic path is the second, more complex ingestion branch. It depends on the same generation pipeline as Phase 1 (which is already built and validated) but introduces web research via Tavily, multi-source synthesis, and elevated hallucination risk. Building it after the URL path is proven means the generation pipeline is a known quantity; only the ingestion layer is new. This is the highest-risk feature and should not be built until the URL path is stable.

**Delivers:** A working session where a user submits a topic description with no URL, the backend researches it via Tavily, synthesizes sources, and produces the same notes/flashcards/quiz output as the URL path.

**Features from FEATURES.md:**
- Topic description input — deep topic research mode (P1)

**Architecture components built:**
- `topic_research.py` — Tavily search → multi-source fetch and merge → synthesis prompt → content validation

**Pitfalls to avoid:**
- Hallucination is highest in this path (no authoritative source URL to ground against); add explicit UI disclaimer: "Content generated from AI knowledge — verify with primary sources"
- Tavily service failures (implement fallback; do not assume 100% uptime)

**Research flag:** NEEDS validation — Tavily pricing and rate limits should be confirmed against current documentation before building. Hallucination mitigation for the topic path needs a defined quality bar and test protocol.

---

### Phase 4: Polish, Hardening, and v1.x Differentiators

**Rationale:** After all three input paths and chat are functional, this phase addresses quality-of-life features, security hardening, performance, and the P2 features that add meaningful value without requiring new infrastructure.

**Delivers:** A production-ready, polished v1 with the most-requested post-launch additions.

**Features from FEATURES.md:**
- Quiz answer explanations — why the correct answer is right (P2)
- Copy to clipboard for notes and flashcards (P2)
- Keyboard navigation for flashcards and quiz (P2)
- Shareable session links with TTL (P2 — requires Redis; add only if user demand confirmed)
- Rate limiting on generation and chat endpoints per IP
- Specific, actionable error messages (paywall detected, timeout, invalid URL format)
- "Looks Done But Isn't" checklist from PITFALLS.md — test against 10+ diverse URL types, 20 quiz reviews, 15-turn chat validation, long article (10k+ words) handling

**Pitfalls to avoid:**
- No rate limiting on generation endpoints (a single user can exhaust LLM budget in minutes)
- Generic error messages that don't help users recover
- XSS from LLM / scraped content rendered as `innerHTML` without DOMPurify

**Research flag:** Standard patterns — polish and hardening have no novel technical decisions; no research phase needed.

---

### Phase Ordering Rationale

- **URL path before topic path** is mandated by the architecture build order from ARCHITECTURE.md: the generation pipeline must be proven end-to-end before the more complex ingestion branch is added. The URL path is also the higher-confidence feature (well-understood extraction patterns, no external search API dependency).
- **Chat after generation** is mandated by feature dependency: chat requires session content to exist and must be designed around real session payloads to validate context-stuffing token sizes.
- **Polish last** is standard — features must exist before they can be hardened and optimized.
- **All critical pitfalls addressed in Phase 1** is a firm recommendation from the research. The pitfall-to-phase mapping in PITFALLS.md is explicit: hallucination, scraping brittleness, context overflow, tutoring mode differentiation, and quiz quality all belong in Phase 1 because retrofitting them is expensive (MEDIUM-HIGH recovery cost) and because launching with any of them unaddressed directly undermines user trust in an educational context.

### Research Flags

Phases needing deeper research during planning:
- **Phase 1:** Jina AI Reader API pricing, rate limits, and failure modes — confirm current plan before building extraction chain. Trafilatura behavior on specific target URL types. Detailed tutoring mode persona specifications — these need to be written and human-reviewed before prompts are coded.
- **Phase 3:** Tavily pricing and API rate limits — verify current pricing against current documentation before committing. Hallucination mitigation strategy for topic path — define quality bar and test protocol explicitly.

Phases with standard patterns (research phase not needed):
- **Phase 2:** SSE in FastAPI is well-documented; context-stuffing for single-session RAG chat is an established pattern with clear trade-offs.
- **Phase 4:** Polish and hardening involve no novel technical decisions; patterns are well-understood.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Core technologies (FastAPI, Pydantic, OpenAI SDK, httpx) are HIGH confidence. Jina Reader availability/pricing is MEDIUM — verify before building. Tavily pricing is MEDIUM — confirm current plan. Library versions correct as of mid-2025; verify on PyPI before installing. |
| Features | MEDIUM | Table stakes and competitive positioning are HIGH confidence (stable market patterns). Competitor-specific feature claims (Khanmigo, Quizlet, StudyFetch) are MEDIUM — based on training data, not live verification. Core feature priority order is HIGH confidence. |
| Architecture | MEDIUM | Stateless backend / stateful frontend, context-stuffing RAG, parallel LLM generation, and SSE streaming are well-established patterns with clear documentation. Confidence is MEDIUM rather than HIGH because WebSearch/WebFetch were unavailable during research; patterns are drawn from training data. |
| Pitfalls | MEDIUM-HIGH | Critical pitfalls (hallucination, scraping brittleness, context overflow, SSRF, prompt injection) are drawn from published sources (OWASP LLM Top 10, Liu et al. "lost in the middle" paper, known scraping failure modes). Web scraping failure patterns are HIGH confidence. LLM hallucination patterns are HIGH confidence. |

**Overall confidence:** MEDIUM

### Gaps to Address

- **Jina Reader availability and pricing:** Research recommends Jina Reader as the primary URL extraction service. Confirm current pricing tier, rate limits, and whether the free tier is adequate for development before committing to it as the primary extraction layer. Fallback to trafilatura-only if Jina pricing is prohibitive.
- **Tavily pricing for topic path:** The topic research path depends on Tavily. Confirm current pricing and request volume limits before Phase 3 planning. If Tavily is too expensive, the fallback is manual: Serper/SerpAPI for search + httpx per result (more complex, but no per-result premium).
- **Tutoring mode persona specifications:** The research identifies this as a pitfall but does not provide the actual persona definitions. These need to be written (reading level targets, analogy policy, sentence length, note structure, question depth) and human-reviewed before Phase 1 prompt engineering begins. This is a content design gap, not a technical gap.
- **Quiz quality validation protocol:** The research recommends human review of 20 generated quizzes across all 3 modes before shipping. This protocol needs to be defined (who reviews, what criteria, what pass/fail threshold) before Phase 1 ends.
- **Token budget calibration:** The architecture recommends a hard ceiling of 8,000-12,000 tokens for LLM input. The actual optimal ceiling depends on observed article lengths and model behavior — calibrate empirically during Phase 1 implementation.

---

## Sources

### Primary (HIGH confidence)
- Python standard library (`asyncio.gather`) — parallel LLM generation pattern
- OWASP LLM Top 10 (2024) — SSRF, prompt injection security pitfalls
- Liu et al., 2023 "Lost in the Middle" — context window degradation pattern

### Secondary (MEDIUM confidence)
- Training data synthesis: FastAPI documentation patterns — SSE via StreamingResponse, async patterns
- Training data synthesis: OpenAI and Anthropic SDK documentation — structured output, JSON mode, streaming
- Training data synthesis: LLM deployment post-mortems (Anthropic, OpenAI, Hugging Face community)
- Training data synthesis: Competitor product analysis — Khanmigo, Quizlet Q-Chat, StudyFetch, Socratic, Photomath, Perplexity, ChatGPT Edu, Notion AI (observed through mid-2025)
- Training data synthesis: Web scraping ecosystem — requests, BeautifulSoup, trafilatura, Playwright known failure modes
- Training data synthesis: Ed-tech feature patterns — active recall, spaced repetition, Bloom's taxonomy implications

### Tertiary (needs live verification)
- Jina AI Reader (`r.jina.ai`) — current pricing and rate limits; verify before Phase 1 implementation
- Tavily (`tavily-python`) — current pricing and request volume limits; verify before Phase 3 planning
- Library versions (`fastapi ^0.115`, `openai ^1.57`, `trafilatura ^2.0`, etc.) — correct as of mid-2025; verify on PyPI before installing

---
*Research completed: 2026-02-18*
*Ready for roadmap: yes*
