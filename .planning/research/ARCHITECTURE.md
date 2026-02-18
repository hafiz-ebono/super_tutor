# Architecture Research

**Domain:** AI Tutoring Web App (LLM pipeline + RAG chat, no persistence)
**Researched:** 2026-02-18
**Confidence:** MEDIUM — derived from established LLM/RAG architectural patterns in training data. WebSearch and WebFetch unavailable during this session; patterns are well-documented in the ecosystem as of training cutoff (Aug 2025) and are unlikely to have fundamentally changed.

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                        │
├──────────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │  Session Form  │  │  Study Page    │  │  Chat Panel        │  │
│  │  (URL/topic +  │  │  Notes | Flash │  │  (RAG chat UI,     │  │
│  │   tutor type)  │  │  cards | Quiz  │  │   streaming)       │  │
│  └───────┬────────┘  └───────┬────────┘  └────────┬───────────┘  │
│          │                   │                    │              │
│          └──────── In-memory session state ───────┘              │
│                   (sessionStorage / JS module)                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────────┐          ┌───────────────────────────────┐ │
│  │  Content Ingestion│          │  LLM Orchestration Layer      │ │
│  │  ─────────────── │          │  ───────────────────────────  │ │
│  │  URL path:        │          │  Prompt builder               │ │
│  │   scrape → clean  │ ──────▶  │  (tutor type × content type) │ │
│  │  Topic path:      │          │  Parallel generation calls    │ │
│  │   web research    │          │  (notes + flashcards + quiz)  │ │
│  └──────────────────┘          └───────────────┬───────────────┘ │
│                                                │                 │
│  ┌─────────────────────────────────────────────▼──────────────┐  │
│  │                    In-Request Session Store                  │  │
│  │  (Python dict / Pydantic model held in response payload)    │  │
│  │  Contains: raw_text, notes, flashcards, quiz, tutor_type    │  │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │                    RAG Chat Handler                          │  │
│  │  /chat endpoint: receives message + session_context         │  │
│  │  Builds prompt: system prompt (session content) + history   │  │
│  │  Calls LLM → streams tokens back via SSE                    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────┬────────────────────────────────────────┘
                           │
            ┌──────────────▼───────────────┐
            │      External Services        │
            ├──────────────────────────────┤
            │  OpenAI / Anthropic API       │
            │  (LLM calls for generation    │
            │   and chat)                   │
            ├──────────────────────────────┤
            │  Web Scraping                 │
            │  (httpx + BeautifulSoup       │
            │   or Playwright for SPAs)     │
            ├──────────────────────────────┤
            │  Web Research (topic path)    │
            │  (Tavily / Serper / DuckDuck  │
            │   Go API → extract + merge)   │
            └──────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Session Form | Capture URL or topic, tutor type selection, initiate session creation | Frontend form with validation; single POST to `/sessions` |
| Study Page | Display notes/flashcards/quiz in tabs; track completion state | In-memory state (JS module or sessionStorage); tab router |
| Chat Panel | Send user messages to backend; display streamed AI responses | SSE or WebSocket client; scroll-locked message list |
| Content Ingestion (URL) | Fetch URL, extract readable text, remove boilerplate | httpx for fetch, trafilatura or BeautifulSoup for extraction |
| Content Ingestion (Topic) | Research topic deeply using web search; aggregate sources | Tavily/Serper API or LLM with browsing; multi-source merge |
| LLM Orchestration | Build prompts per tutor type; call LLM for notes, flashcards, quiz | FastAPI service layer; prompt templates + LLM SDK calls |
| Prompt Builder | Compose system + user prompts per content type and tutor type | Python string templates or Jinja2; tutor_type as parameter |
| RAG Chat Handler | Accept chat message + session context; stream response | FastAPI SSE endpoint; session content as system prompt |
| In-Request Session Store | Hold generated session data for the lifetime of a request | Pydantic response model returned to frontend; no server-side DB |

---

## Recommended Project Structure

```
backend/
├── app/
│   ├── main.py                # FastAPI app instantiation, middleware, router mounts
│   ├── config.py              # Settings (API keys, model names, env vars)
│   ├── models/
│   │   ├── session.py         # Pydantic: SessionRequest, SessionResponse, ChatMessage
│   │   └── content.py         # Pydantic: ExtractedContent, ResearchResult
│   ├── routers/
│   │   ├── sessions.py        # POST /sessions — orchestrates ingestion + generation
│   │   └── chat.py            # POST /chat — RAG chat, SSE streaming
│   ├── services/
│   │   ├── ingestion/
│   │   │   ├── url_ingestion.py    # Scrape + extract from URL
│   │   │   └── topic_research.py   # Multi-source web research
│   │   ├── generation/
│   │   │   ├── notes.py            # Generate notes via LLM
│   │   │   ├── flashcards.py       # Generate flashcards via LLM
│   │   │   └── quiz.py             # Generate quiz via LLM
│   │   ├── prompt_builder.py       # Compose prompts per tutor type + content type
│   │   └── chat_service.py         # RAG chat handler + SSE stream
│   └── utils/
│       ├── text_cleaner.py    # Normalize extracted text, truncate to token budget
│       └── llm_client.py      # Thin wrapper around OpenAI/Anthropic SDK

frontend/
├── src/
│   ├── pages/
│   │   ├── Home.tsx           # Session creation form
│   │   └── Study.tsx          # Study page (tabs: Notes | Flashcards | Quiz)
│   ├── components/
│   │   ├── SessionForm/       # URL/topic input, tutor type selector
│   │   ├── Notes/             # Rendered notes panel
│   │   ├── Flashcards/        # Flashcard carousel with completion tracking
│   │   ├── Quiz/              # MC quiz with scoring
│   │   └── Chat/              # Chat panel with SSE streaming
│   ├── state/
│   │   └── session.ts         # Session state (notes, flashcards, quiz, chat history)
│   └── api/
│       └── client.ts          # API calls to backend (POST /sessions, POST /chat)
```

### Structure Rationale

- **services/ingestion/:** The two content paths (URL vs. topic) are meaningfully different in implementation; keeping them separate makes each independently testable and swappable.
- **services/generation/:** Notes, flashcards, and quiz have different output schemas and prompt structures. Separate files avoid a monolithic "generate everything" function.
- **prompt_builder.py:** Centralizing prompt composition means tutor type logic lives in exactly one place. Adding a new tutor type is a one-file change.
- **utils/llm_client.py:** A thin wrapper decouples the rest of the code from SDK-specific signatures, making model switches (e.g., OpenAI → Anthropic) cheap.
- **state/session.ts:** All session data flows into one module. No prop-drilling. Components subscribe or import directly.

---

## Architectural Patterns

### Pattern 1: Stateless Backend, Stateful Frontend

**What:** The backend generates session content in a single request and returns the full session payload. The frontend owns session state for the lifetime of the browser session. No server-side session storage is needed.

**When to use:** V1 with no auth and no persistence requirement. Dramatically simplifies the backend.

**Trade-offs:**
- Pro: No DB, no session management, no auth surface
- Pro: Scales to any number of concurrent users trivially
- Con: Refreshing the page loses the session (acceptable for v1 ephemeral requirement)
- Con: Chat history must also be managed client-side and sent back with each chat request

**Example (session state in frontend):**
```typescript
// state/session.ts
export interface SessionState {
  raw_content: string;          // kept for sending to chat endpoint
  tutor_type: 'micro' | 'kid' | 'advanced';
  notes: string;
  flashcards: Flashcard[];
  quiz: QuizQuestion[];
  chat_history: ChatMessage[];
}

// Stored in module-level variable or sessionStorage
let session: SessionState | null = null;

export function setSession(s: SessionState) { session = s; }
export function getSession() { return session; }
```

**Example (backend response — no stored state):**
```python
# routers/sessions.py
@router.post("/sessions", response_model=SessionResponse)
async def create_session(req: SessionRequest) -> SessionResponse:
    content = await ingest(req)          # URL scrape or topic research
    notes, flashcards, quiz = await asyncio.gather(
        generate_notes(content, req.tutor_type),
        generate_flashcards(content, req.tutor_type),
        generate_quiz(content, req.tutor_type),
    )
    return SessionResponse(
        raw_content=content.text,
        notes=notes,
        flashcards=flashcards,
        quiz=quiz,
    )
```

---

### Pattern 2: Context-Stuffing RAG (No Vector DB)

**What:** For the in-session chat, instead of embedding + retrieving chunks (traditional RAG with a vector store), pass the full session content as the system prompt. The LLM reasons over the whole document in-context.

**When to use:** When session content fits within the model's context window (typically 16k–128k tokens), and there is no persistent knowledge base. This is the right default for v1 — vector DBs add significant complexity for no benefit at this scale.

**Trade-offs:**
- Pro: No vector DB, no embedding pipeline, no retrieval step
- Pro: LLM sees the full document — no chunking artifacts or missed passages
- Con: Cost scales with document length per chat message
- Con: Very long documents (>80k tokens) may need truncation strategies
- Con: Not suitable if sessions need to be retrieved later (they don't in v1)

**Example (chat endpoint):**
```python
# services/chat_service.py
async def chat(message: str, session_content: str,
               history: list[ChatMessage], tutor_type: str):
    system_prompt = f"""You are a tutor helping a student understand the following material.
Tutoring style: {tutor_type}.
Answer only based on the content below. If the answer isn't in the content, say so.

---
{session_content}
---"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": message})

    # Stream tokens back via SSE
    async for chunk in llm_client.stream(messages):
        yield chunk
```

---

### Pattern 3: Parallel LLM Generation

**What:** Notes, flashcards, and quiz are independent — they all derive from the same extracted content. Fire all three LLM calls concurrently using `asyncio.gather`. Do not generate them serially.

**When to use:** Always, for this use case. Serial generation is 3x slower with no benefit.

**Trade-offs:**
- Pro: Generation time is max(notes_time, flashcards_time, quiz_time) instead of the sum
- Con: 3x token throughput simultaneously — stay within rate limits; add retry logic

**Example:**
```python
notes, flashcards, quiz = await asyncio.gather(
    generate_notes(content, tutor_type),
    generate_flashcards(content, tutor_type),
    generate_quiz(content, tutor_type),
)
```

---

### Pattern 4: Structured LLM Output with Pydantic Validation

**What:** Instruct the LLM to return JSON matching your schema. Validate with Pydantic. Retry on parse failure.

**When to use:** For flashcard and quiz generation where structured data is required. Notes can be markdown (unstructured).

**Trade-offs:**
- Pro: Reliable data shapes on the frontend; no fragile parsing
- Con: Adds latency on retry; JSON mode / function calling reduces failure rate significantly
- Con: Some models are more reliable than others for structured output

**Example:**
```python
from pydantic import BaseModel

class Flashcard(BaseModel):
    front: str
    back: str

class FlashcardSet(BaseModel):
    flashcards: list[Flashcard]

# Use OpenAI structured outputs or response_format={"type": "json_object"}
# Then: FlashcardSet.model_validate_json(response)
```

---

### Pattern 5: Prompt Builder Centralization

**What:** Tutor type (Micro / Kid / Advanced) adjusts tone and complexity across all three content types. Centralize this logic in a `prompt_builder.py` module that injects tutor type instructions into each prompt template.

**When to use:** Always for this app — avoids duplication across notes/flashcards/quiz generators and makes adding new tutor types trivial.

**Example:**
```python
# services/prompt_builder.py
TUTOR_TYPE_INSTRUCTIONS = {
    "micro": "Be extremely concise. Use bullet points. Focus on key takeaways only.",
    "kid": "Explain simply, use analogies, avoid jargon. Friendly tone.",
    "advanced": "Be comprehensive. Include nuance, edge cases, and expert-level depth.",
}

def build_notes_prompt(content: str, tutor_type: str) -> str:
    style = TUTOR_TYPE_INSTRUCTIONS[tutor_type]
    return f"""Generate structured study notes from the following content.
Style instruction: {style}

Content:
{content}"""
```

---

## Data Flow

### Session Creation Flow

```
User submits form (URL/topic + tutor_type)
    ↓
Frontend: POST /sessions {input_type, value, tutor_type}
    ↓
Backend: Content Ingestion
    ├── URL path:   httpx.get(url) → extract text → clean → normalize
    └── Topic path: web_search(topic) → fetch top N pages → merge text → summarize
    ↓
Backend: text_cleaner.truncate_to_token_budget(text, max_tokens=60000)
    ↓
Backend: asyncio.gather(
    generate_notes(content, tutor_type),       → LLM call → markdown string
    generate_flashcards(content, tutor_type),  → LLM call → JSON → Flashcard[]
    generate_quiz(content, tutor_type),        → LLM call → JSON → QuizQuestion[]
)
    ↓
Backend: SessionResponse {raw_content, notes, flashcards, quiz}
    ↓
Frontend: setSession(response) → navigate to /study
    ↓
Study Page renders Notes | Flashcards | Quiz tabs from in-memory state
```

### RAG Chat Flow

```
User types message in chat panel
    ↓
Frontend: POST /chat {message, session_content, chat_history, tutor_type}
    ↓
Backend: chat_service.chat(message, session_content, history, tutor_type)
    ├── Build system prompt: tutor_type instructions + full session_content
    ├── Append chat history to messages array
    └── Append new user message
    ↓
LLM API: streaming call
    ↓
Backend: SSE stream — yield token chunks
    ↓
Frontend: EventSource reads chunks → append to chat message in real time
    ↓
Frontend: On stream end → add complete message to chat_history state
```

### State Management (Frontend)

```
sessionStorage (or module-level var)
    ↓ (read on Study page mount)
session: SessionState
    ├── raw_content     → sent with every /chat request
    ├── notes           → rendered in Notes tab
    ├── flashcards[]    → Flashcard component, completion tracked locally
    ├── quiz[]          → Quiz component, score tracked locally
    └── chat_history[]  → Chat panel, updated on each exchange
```

### Key Data Flows Summary

1. **Content ingestion → generation:** Raw extracted text flows as a string into three parallel LLM calls. No intermediate storage. The text is cleaned/truncated before LLM calls.
2. **Session response → frontend state:** The full session payload (including raw_content) is stored client-side. raw_content is re-sent on every chat request — the backend is stateless.
3. **Chat:** Frontend owns history. Each /chat request sends the full history + full raw_content. Backend reconstructs the full prompt on every call.

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0–100 users (launch) | Current stateless design is sufficient. Single FastAPI process. No DB, no queue. |
| 100–1k concurrent | Add async LLM call pooling. Rate-limit per-IP to avoid LLM quota exhaustion. Consider caching scraped URLs (in-process dict, TTL 10 min). |
| 1k–10k concurrent | Add Redis for URL scrape caching. Move to Gunicorn + multiple Uvicorn workers. Add background task queue (Celery/ARQ) for generation if response time becomes unacceptable. |
| 10k+ concurrent | Consider separating ingestion and generation into microservices. Add CDN for static assets. Evaluate streaming generation results (partial SSE) for perceived performance. |

### Scaling Priorities

1. **First bottleneck: LLM API rate limits.** OpenAI/Anthropic enforce tokens-per-minute and requests-per-minute limits. Parallel generation of 3 outputs per session hits this fast. Mitigation: exponential backoff + retry, spread across multiple API keys if needed.
2. **Second bottleneck: URL scraping latency.** External sites can be slow. Mitigation: async scraping with timeout (5–10s), cache recently scraped URLs in-memory.
3. **Third bottleneck: chat context size.** Sending full session content on every chat message is expensive as sessions get longer. Mitigation: truncate raw_content to a max token budget before sending; summarize older chat history if it grows long.

---

## Anti-Patterns

### Anti-Pattern 1: Storing Session State Server-Side Without Auth

**What people do:** Save session data in a server-side dict or DB keyed by a session ID, return just the ID to the frontend.

**Why it's wrong:** Without auth, any session ID can be guessed or leaked. You've added DB complexity and a security surface for zero benefit in v1. The session data is not sensitive enough to protect this way.

**Do this instead:** Return the full session payload in the HTTP response. Let the frontend own the state. The backend stays stateless and trivially scalable.

---

### Anti-Pattern 2: Building a Traditional Vector RAG Pipeline for a Single Session

**What people do:** Embed the session content, store chunks in a vector DB (Chroma, Pinecone, Weaviate), run semantic search on each chat message, inject retrieved chunks into the prompt.

**Why it's wrong:** For a single session where all content fits in the LLM's context window (which it does for article/doc URLs), this is massive over-engineering. Vector DBs require embedding infrastructure, storage, and retrieval tuning — none of which pay off when you can just send the whole document as a system prompt.

**Do this instead:** Context stuffing (Pattern 2). Pass the full session content as the system prompt. Revisit vector RAG only if sessions grow to 200k+ tokens or if a persistent multi-document knowledge base is introduced.

---

### Anti-Pattern 3: Serial LLM Generation

**What people do:** Generate notes, then await, then generate flashcards, then await, then generate quiz. Sequential.

**Why it's wrong:** Adds 2–3x latency unnecessarily. A user waits 15–30 seconds instead of 5–10 seconds. The three generation calls have no data dependency on each other.

**Do this instead:** `asyncio.gather(generate_notes(...), generate_flashcards(...), generate_quiz(...))` — always parallel.

---

### Anti-Pattern 4: Embedding Tutor Type Logic in Every Generator

**What people do:** Each of notes.py, flashcards.py, quiz.py has its own if/elif tutor_type block with hardcoded strings.

**Why it's wrong:** Adding a new tutor type requires changes in three files. Tutor type descriptions drift apart. Hard to maintain.

**Do this instead:** One `prompt_builder.py` with a single TUTOR_TYPE_INSTRUCTIONS dict. Each generator calls `prompt_builder.build_X_prompt(content, tutor_type)`. Tutor type changes happen in exactly one place.

---

### Anti-Pattern 5: Unguarded LLM Output (No Schema Validation)

**What people do:** Trust the LLM to return valid JSON for flashcards and quiz; parse it with `json.loads()` directly; crash on malformed output.

**Why it's wrong:** LLMs occasionally produce malformed JSON, truncated output, or markdown-wrapped JSON. Without validation, this surfaces as 500 errors or broken frontend state.

**Do this instead:** Use Pydantic models + `model_validate_json()`. Use the LLM's JSON mode or structured output feature (OpenAI `response_format={"type": "json_object"}` or Anthropic tool use). Add a retry loop (max 2 retries) on parse failure before raising.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| OpenAI / Anthropic API | Direct SDK calls (openai, anthropic Python packages). Async clients for FastAPI. | Use a thin `llm_client.py` wrapper; don't scatter SDK calls across services. Store API key in env var. |
| URL Scraping | `httpx.AsyncClient` for fetch; `trafilatura` or `BeautifulSoup` for extraction | trafilatura is purpose-built for article extraction — better than raw BeautifulSoup for boilerplate removal. Timeout at 10s. |
| Web Research (topic path) | Tavily API (search + content extraction in one call) or manual: search API + httpx per result | Tavily is the easiest integration for LLM research pipelines; returns clean text per result. Fallback: Serper/SerpAPI + manual fetch. |
| Frontend ↔ Backend (generation) | REST: POST /sessions returns full JSON payload | Keep it simple — no WebSocket needed for the initial generation flow. |
| Frontend ↔ Backend (chat) | SSE: POST /chat initiates stream; frontend uses EventSource or `fetch` with `ReadableStream` | SSE is simpler than WebSocket for one-directional streaming (server → client). FastAPI supports SSE via `StreamingResponse`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Router ↔ Service layer | Direct function call (async) | Routers are thin — they validate input and call services. No business logic in routers. |
| Ingestion → Generation | Python function argument (string: the extracted text) | No queue, no event bus. Ingestion returns a string; generation takes a string. Simple and synchronous within a single request. |
| Generation services ↔ LLM client | Direct async function call | All generators go through `llm_client.py`. LLM provider is swappable in one place. |
| Chat service ↔ Frontend | SSE stream | `StreamingResponse` in FastAPI; frontend reads with `fetch` + `ReadableStream` or `EventSource`. Chat history round-trips as JSON in the request body each time. |
| Frontend state ↔ Components | Module-level state or sessionStorage | No Redux/Zustand needed for v1. A simple module export with get/set functions is sufficient. |

---

## Build Order (Dependencies)

The component dependency graph implies this build sequence:

```
1. LLM Client wrapper (llm_client.py)
       ↓
2. Content Ingestion — URL path (url_ingestion.py + text_cleaner.py)
       ↓
3. Prompt Builder (prompt_builder.py)
       ↓
4. Generation services (notes.py, flashcards.py, quiz.py)  ← parallel, but after 1–3
       ↓
5. Session router (POST /sessions) — wires ingestion → generation → response
       ↓
6. Frontend: Session Form + Study Page shell (tabs, no real data)
       ↓
7. Frontend: Notes, Flashcards, Quiz components (connect to real session data)
       ↓
8. Chat service (chat_service.py) + chat router (POST /chat with SSE)
       ↓
9. Frontend: Chat Panel (SSE client, history management)
       ↓
10. Content Ingestion — Topic path (topic_research.py)  ← last, independent of chat
```

**Rationale for this order:**
- The LLM client is the foundation — everything else calls it.
- URL ingestion before topic research: URL path is simpler (no external search API needed) and validates the generation pipeline end-to-end first.
- Prompt builder before generation: generation services can't be written without it.
- Session router after all generation services: can't wire them together until they exist.
- Frontend shell before connecting real data: enables visual layout testing before backend is ready.
- Chat last: it's architecturally independent of generation; adds the SSE complexity after the main flow is stable.
- Topic path last: requires external search API setup and is the more complex ingestion path.

---

## Sources

- LLM/RAG architectural patterns: training knowledge (MEDIUM confidence — well-established patterns as of Aug 2025 training cutoff; WebSearch/WebFetch unavailable during this session)
- FastAPI async streaming (SSE via StreamingResponse): established FastAPI documentation pattern (MEDIUM confidence — stable API, unlikely to have changed)
- Context-stuffing vs. vector RAG tradeoff: widely documented community pattern for single-document use cases (MEDIUM confidence)
- asyncio.gather for parallel LLM calls: Python standard library, well-documented (HIGH confidence)
- Pydantic structured output validation: established pattern with OpenAI/Anthropic SDKs (MEDIUM confidence)
- trafilatura for article extraction: well-established library, recommended for article extraction over raw BeautifulSoup (MEDIUM confidence)

---
*Architecture research for: AI Tutoring Web App (Super Tutor)*
*Researched: 2026-02-18*
