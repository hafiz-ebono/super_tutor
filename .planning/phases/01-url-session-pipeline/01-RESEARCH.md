# Phase 1: URL Session Pipeline - Research

**Researched:** 2026-02-18
**Domain:** FastAPI + Agno workflow pipeline + URL content extraction + Next.js App Router + SSE progress streaming
**Confidence:** MEDIUM-HIGH (core stack verified; Agno streaming patterns partially from docs, partially inferred from community)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Session creation form**
- Landing page is a marketing/intro page with a CTA that leads to a dedicated create page (e.g., /create)
- Create page has all three fields on one screen: URL input, tutoring mode picker, and optional focus prompt — submitted together
- Tutoring mode presented as three selectable cards with brief descriptions (Micro Learning, Teaching a Kid, Advanced)
- Focus prompt field labeled "What do you want to focus on?" — clearly optional, free-text hint to guide the AI's emphasis

**Progress experience**
- On submit, the create page transitions to a full-screen loading state (not an overlay)
- Step messages use a friendly, slightly playful tone: "Reading the article...", "Crafting your notes...", "Making your flashcards...", "Building your quiz..."
- A simple progress bar at the top of the loading screen advances as each step completes
- On generation complete, user is automatically redirected to the study page — no button required

**Study page layout**
- Left sidebar navigation — user clicks Notes, Flashcards, or Quiz in the sidebar to switch content areas
- Sidebar shows: source title and tutoring mode label only (no URL, no timestamp)
- Sidebar includes a "New session" link so the user can easily start over
- Notes section: structured markdown — headings, bullet points, bold key terms — reads like a formatted study guide
- Flashcards section: grid layout showing all cards with the question side visible (flip interaction is Phase 3)
- Quiz section: multiple choice, one question at a time — user answers, sees instant feedback (correct/wrong), moves to next
- After quiz completion: score summary (X/Y correct) followed by review of each question showing the correct answer

**URL failure & fallback**
- When URL extraction fails, user is returned to the create form with an inline error below the URL field
- Error messaging: friendly top-level message ("We couldn't read that page") with a specific pointer beneath it indicating the likely cause (paywall, invalid URL, empty/unreadable page)
- A textarea appears inline below the error message: "Paste the article text instead" — user can paste content and resubmit
- When fallback textarea appears, mode selection and focus prompt remain filled in — only the URL field is cleared
- After paste submission, user goes through the same full-screen progress screen as the URL path — consistent experience

**URL extraction chain (from STATE.md)**
- Jina Reader -> trafilatura -> Playwright -> paste-text fallback

### Claude's Discretion
- Textarea character limit and input guidance (minimum length, max length hints)
- Handling of bad/garbled pasted text (client-side validation threshold or pass-through to agents)
- Exact progress bar segment widths and animation style
- Copy for the landing page CTA and create page headings
- Error pointer message wording for each failure type

### Deferred Ideas (OUT OF SCOPE)
- Session history and multi-session support — user requested the ability to store generated sessions and navigate between them from a home/dashboard view. This is a meaningful capability on its own and belongs in a future phase.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SESS-01 | User can create a session by providing an article/doc URL and a focus prompt describing what to study | URL extraction chain (Jina -> trafilatura -> Playwright), FastAPI POST /sessions endpoint |
| SESS-03 | User selects a tutoring type (Micro Learning / Teaching a Kid / Advanced) before generating a session; this adapts tone and complexity of all generated content | System prompt per tutoring type injected into all three Agno agents at workflow time |
| SESS-04 | If URL scraping fails (paywall, empty page, invalid URL), user is shown a specific error message and offered a paste-text fallback to continue | Extraction chain returns None -> categorized error -> SSE error event -> frontend renders fallback textarea |
| SESS-05 | User sees step-by-step progress feedback during AI generation | sse-starlette EventSourceResponse + Agno workflow StepStarted events + manual yield RunResponse for named steps |
| GEN-01 | AI generates structured notes from the session content, adapted to the selected tutoring type | Agno Agent with notes-focused system prompt, tutoring-type persona injected, output is markdown |
| GEN-02 | AI generates flashcards from the session content, adapted to the selected tutoring type | Agno Agent with flashcard-focused system prompt, structured output (list of {front, back} objects) |
| GEN-03 | AI generates a multiple-choice quiz (4 options per question, one correct answer) from the session content, adapted to the selected tutoring type | Agno Agent with quiz-focused system prompt, structured output (list of {question, options[4], answer_index}) |
| STUDY-01 | All study materials presented on a single page with tab navigation | Next.js study page with left sidebar (Notes / Flashcards / Quiz links), client-side tab state |
| AGENT-01 | All AI agents built with the Agno framework | Agno 2.5.2 Workflow class wrapping three Agent instances |
| AGENT-02 | AI provider, model, and API key configurable via environment variables — switching providers requires only a config change | pydantic-settings Settings class reads AGENT_PROVIDER, AGENT_MODEL, API key env vars; model factory function resolves to Agno model object |
</phase_requirements>

---

## Summary

Phase 1 is a full-stack feature build across two codebases: a Python FastAPI backend hosting Agno workflow agents, and a Next.js frontend. The critical path is: POST /sessions -> trigger Agno workflow -> stream SSE progress events -> redirect to study page. Every locked decision is implementable with well-understood patterns — the only moderate-complexity area is the URL extraction chain (Jina -> trafilatura -> Playwright) and wiring Agno workflow step events into FastAPI SSE.

The stack is stable and well-documented. Agno 2.5.2 is the latest release (February 15, 2026). Next.js App Router with EventSource is the modern standard for SSE on the frontend. The OAT UI library (oat.ink) is a vanilla HTML/CSS zero-dependency library — it is not a React component library — which means all interactive study-page components (tabs, quiz, progress bar) must be built as plain React/Tailwind with OAT UI's CSS layered in. This is the single most important planning implication: no ready-made React component library to lean on for the study page.

**Primary recommendation:** Build the backend as a FastAPI app with a single `/sessions` SSE endpoint that streams Agno workflow events. Store session data in memory (dict keyed by session_id) for this phase — no database needed. On the frontend, use Next.js App Router with `EventSource` and `useState`/`useEffect` for the loading page, then a simple client component with sidebar state for the study page. OAT UI CSS provides base styling; interactive components are hand-rolled React.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| agno | 2.5.2 (Feb 2026) | AI workflow orchestration, agent definition | Required by AGENT-01; active, well-documented, Python-native |
| fastapi | latest (0.115.x) | HTTP server, SSE endpoint, REST API | Required by project; standard Python API framework |
| sse-starlette | 3.2.0 (Jan 2026) | SSE response type for FastAPI/Starlette | Production-ready, W3C-compliant, widely used with FastAPI |
| pydantic-settings | 2.x | Environment variable / .env config management | FastAPI's official recommendation for settings; type-safe |
| trafilatura | 2.0.0 | URL HTML->text extraction (layer 2 of chain) | Top-ranked open-source extractor; used by HuggingFace, IBM |
| playwright (python) | latest | Headless browser for JS-rendered pages (layer 3) | Only option for dynamic-content pages that Jina/trafilatura cannot handle |
| Next.js | 15.x | Frontend framework | Project standard; App Router with server/client components |
| react-markdown | latest | Render AI-generated markdown notes in React | De facto standard; safe, composable, handles GFM |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | latest | Async HTTP client for Jina Reader requests | Required: Jina Reader is an HTTP API called from FastAPI |
| python-dotenv | latest | Load .env in local dev (pydantic-settings handles prod) | Local development only |
| remark-gfm | latest | GitHub Flavored Markdown plugin for react-markdown | Enable tables, strikethrough in notes |
| uvicorn | latest | ASGI server to run FastAPI | Standard FastAPI runner |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sse-starlette | Plain StreamingResponse + manual SSE formatting | sse-starlette handles reconnection, event IDs, retry headers correctly; StreamingResponse requires hand-rolling the SSE protocol |
| trafilatura | newspaper3k, goose3 | trafilatura has highest F1 in benchmarks; the others are older and less accurate on modern sites |
| Playwright (layer 3) | Selenium, Requests-HTML | Playwright async-first, actively maintained, handles SPAs better |
| react-markdown | @next/mdx, custom renderer | react-markdown is safe (no XSS risk from AI output), component-mappable, works with dynamic content |

**Installation:**
```bash
# Backend
pip install agno sse-starlette fastapi uvicorn pydantic-settings httpx trafilatura playwright python-dotenv
playwright install chromium

# Frontend
npm install react-markdown remark-gfm
```

---

## Architecture Patterns

### Recommended Project Structure

```
super_tutor/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router mounts
│   │   ├── config.py            # pydantic-settings Settings class
│   │   ├── routers/
│   │   │   └── sessions.py      # POST /sessions SSE endpoint
│   │   ├── agents/
│   │   │   ├── model_factory.py # get_model() reads AGENT_PROVIDER/MODEL env vars
│   │   │   ├── personas.py      # Tutoring type system prompt strings
│   │   │   ├── notes_agent.py   # Agno Agent for notes generation
│   │   │   ├── flashcard_agent.py
│   │   │   └── quiz_agent.py
│   │   ├── workflows/
│   │   │   └── session_workflow.py  # Agno Workflow orchestrating all three agents
│   │   ├── extraction/
│   │   │   ├── chain.py         # extract_content(url) -> text | ExtractionError
│   │   │   ├── jina.py          # Layer 1: Jina Reader via httpx
│   │   │   ├── trafilatura_extractor.py   # Layer 2: trafilatura.fetch_url + extract
│   │   │   └── playwright_extractor.py    # Layer 3: async Playwright page.content()
│   │   └── models/
│   │       └── session.py       # Pydantic models: SessionRequest, SessionResult
│   ├── .env                     # Local dev env vars (gitignored)
│   └── requirements.txt
└── frontend/
    └── src/
        └── app/
            ├── page.tsx             # Landing/marketing page
            ├── create/
            │   └── page.tsx         # Session creation form (client component)
            ├── loading/
            │   └── page.tsx         # Full-screen loading state with SSE + progress bar
            └── study/
                └── [sessionId]/
                    └── page.tsx     # Study page: sidebar + Notes/Flashcards/Quiz
```

### Pattern 1: Configurable Model Factory (AGENT-02)

**What:** A single factory function reads `AGENT_PROVIDER` and `AGENT_MODEL` from environment, returns the correct Agno model object. All agents call this function — switching providers requires only `.env` changes.

**When to use:** Every agent instantiation in `notes_agent.py`, `flashcard_agent.py`, `quiz_agent.py`

```python
# Source: Agno GitHub README (github.com/agno-agi/agno) + provider import patterns
# backend/app/agents/model_factory.py
import os
from agno.models.openai import OpenAIChat
from agno.models.anthropic import Claude
from agno.models.groq import Groq

def get_model():
    provider = os.environ.get("AGENT_PROVIDER", "openai").lower()
    model_id = os.environ.get("AGENT_MODEL", "gpt-4o")

    if provider == "anthropic":
        return Claude(id=model_id)
    elif provider == "groq":
        return Groq(id=model_id)
    else:
        return OpenAIChat(id=model_id)
```

```bash
# .env — switching to Claude requires only these changes, no code edit
AGENT_PROVIDER=anthropic
AGENT_MODEL=claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...
```

### Pattern 2: URL Extraction Chain

**What:** Try Jina Reader first (fast, no browser), fall back to trafilatura (local library), then Playwright (real browser). Return classified error if all three fail.

**When to use:** Start of every session creation where a URL is provided

```python
# Source: Jina Reader GitHub (github.com/jina-ai/reader),
#         trafilatura docs (trafilatura.readthedocs.io/en/latest/quickstart.html),
#         Playwright Python docs (playwright.dev/python)
# backend/app/extraction/chain.py
import httpx
import trafilatura

class ExtractionError(Exception):
    def __init__(self, kind: str, message: str):
        self.kind = kind  # "paywall" | "invalid_url" | "empty" | "unreachable"
        self.message = message

async def extract_content(url: str, jina_api_key: str) -> str:
    # Layer 1: Jina Reader — fast, no browser needed
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",
                headers={"Authorization": f"Bearer {jina_api_key}"},
            )
        content = resp.text.strip()
        if content and len(content) > 200:
            return content
    except Exception:
        pass

    # Layer 2: trafilatura — best open-source HTML extractor
    downloaded = trafilatura.fetch_url(url)
    if downloaded:
        text = trafilatura.extract(downloaded, include_tables=True, output_format="markdown")
        if text and len(text) > 200:
            return text

    # Layer 3: Playwright — handles JS-heavy SPAs
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, timeout=20000)
            await page.wait_for_load_state("networkidle")
            html = await page.content()
            await browser.close()
        text = trafilatura.extract(html, output_format="markdown")
        if text and len(text) > 200:
            return text
    except Exception:
        pass

    raise ExtractionError(
        kind=_classify_failure(url),
        message="Could not extract readable content from this URL"
    )

def _classify_failure(url: str) -> str:
    # Heuristic — LOW confidence; refine based on real failures observed in dev
    paywall_domains = ["nytimes.com", "wsj.com", "ft.com", "bloomberg.com", "economist.com"]
    if any(d in url for d in paywall_domains):
        return "paywall"
    if not url.startswith(("http://", "https://")):
        return "invalid_url"
    return "empty"
```

**Failure detection:** `trafilatura.extract()` returns `None` when content cannot be pulled. Jina Reader returns short/empty text for paywalled or empty pages. The 200-character threshold is a practical heuristic — adjust based on real failures observed in development.

### Pattern 3: Agno Workflow with Progress Streaming

**What:** Agno `Workflow` subclass with a `run()` generator. Yields `RunResponse` objects with custom content strings between agent calls to emit named progress steps.

**When to use:** Session generation pipeline

```python
# Source: Agno docs (docs.agno.com/workflows/introduction),
#         bitdoze.com Agno Workflow article
# backend/app/workflows/session_workflow.py
from agno.workflow import Workflow
from agno.run.response import RunResponse, RunEvent
from agno.agent import Agent
from typing import Iterator

class SessionWorkflow(Workflow):
    description: str = "Generate study materials from extracted content"
    notes_agent: Agent
    flashcard_agent: Agent
    quiz_agent: Agent

    def run(self, content: str, tutoring_type: str, focus_prompt: str) -> Iterator[RunResponse]:
        input_text = f"Content:\n{content}\n\nFocus on: {focus_prompt}" if focus_prompt else f"Content:\n{content}"

        # Progress message before notes generation
        yield RunResponse(event=RunEvent.workflow_started, content="Crafting your notes...")
        notes_result = self.notes_agent.run(input_text)
        notes = notes_result.content

        # Progress message before flashcard generation
        yield RunResponse(event=RunEvent.running, content="Making your flashcards...")
        flashcard_result = self.flashcard_agent.run(input_text)
        flashcards = flashcard_result.content

        # Progress message before quiz generation
        yield RunResponse(event=RunEvent.running, content="Building your quiz...")
        quiz_result = self.quiz_agent.run(input_text)
        quiz = quiz_result.content

        # Final payload with all generated content
        yield RunResponse(
            event=RunEvent.workflow_completed,
            content={"notes": notes, "flashcards": flashcards, "quiz": quiz}
        )
```

**Note on RunEvent values:** `workflow_started` and `workflow_completed` are confirmed in Agno docs. `RunEvent.running` is inferred — verify against the installed package enum. If it does not exist, using `workflow_started` for intermediate steps will still work since the frontend only reads `content`, not `event`.

### Pattern 4: FastAPI SSE Endpoint

**What:** POST endpoint receives session params, streams SSE events via sse-starlette as the workflow progresses.

**When to use:** The single session creation endpoint the frontend calls

```python
# Source: sse-starlette PyPI (pypi.org/project/sse-starlette),
#         FastAPI CORS docs (fastapi.tiangolo.com/tutorial/cors)
# backend/app/routers/sessions.py
import asyncio, json, uuid
from fastapi import APIRouter
from sse_starlette import EventSourceResponse
from app.extraction.chain import extract_content, ExtractionError
from app.workflows.session_workflow import SessionWorkflow
from agno.run.response import RunEvent

router = APIRouter()
SESSION_STORE: dict = {}  # In-memory store — Phase 1 only, no database

@router.post("/sessions")
async def create_session(request: SessionRequest):
    session_id = str(uuid.uuid4())

    async def event_generator():
        yield {"event": "progress", "data": json.dumps({"message": "Reading the article..."})}

        try:
            content = await extract_content(request.url, settings.jina_api_key)
        except ExtractionError as e:
            yield {"event": "error", "data": json.dumps({"kind": e.kind})}
            return

        workflow = build_workflow(request.tutoring_type)
        for response in workflow.run(
            content=content,
            tutoring_type=request.tutoring_type,
            focus_prompt=request.focus_prompt or ""
        ):
            if response.event == RunEvent.workflow_completed:
                SESSION_STORE[session_id] = response.content
                yield {"event": "complete", "data": json.dumps({"session_id": session_id})}
            else:
                # Mid-workflow progress messages
                yield {"event": "progress", "data": json.dumps({"message": response.content})}
            await asyncio.sleep(0)  # yield to event loop so SSE frames flush

    return EventSourceResponse(event_generator())
```

**CORS setup in main.py:**
```python
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # ["http://localhost:3000"] in dev
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

### Pattern 5: Frontend SSE + Progress Bar (Next.js Client Component)

**What:** Client component opens EventSource, tracks step index with useState, advances progress bar on each `progress` event, redirects on `complete`.

**When to use:** `/loading` page shown immediately after form submit

```typescript
// Source: Upstash blog SSE + Next.js (upstash.com/blog/sse-streaming-llm-responses),
//         Pedro Alonso blog (pedroalonso.net/blog/sse-nextjs-real-time-notifications)
// frontend/src/app/loading/page.tsx
"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";

const STEPS = [
  "Reading the article...",
  "Crafting your notes...",
  "Making your flashcards...",
  "Building your quiz...",
];

export default function LoadingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [stepIndex, setStepIndex] = useState(0);
  const [currentMessage, setCurrentMessage] = useState(STEPS[0]);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    // Two-step approach: POST first to get session stream URL
    const es = new EventSource(
      `${process.env.NEXT_PUBLIC_API_URL}/sessions/stream?session_id=${searchParams.get("session_id")}`
    );
    esRef.current = es;

    es.addEventListener("progress", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setCurrentMessage(data.message);
      setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
    });

    es.addEventListener("complete", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      es.close();
      router.push(`/study/${data.session_id}`);
    });

    es.addEventListener("error", (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      es.close();
      router.push(`/create?error=${data.kind}`);
    });

    return () => es.close();
  }, []);

  const progress = ((stepIndex + 1) / STEPS.length) * 100;

  return (
    <div className="loading-screen">
      <div className="progress-track">
        <div
          className="progress-fill"
          style={{ width: `${progress}%`, transition: "width 400ms ease-in-out" }}
        />
      </div>
      <p className="step-message">{currentMessage}</p>
    </div>
  );
}
```

**EventSource POST limitation:** Browser-native `EventSource` only supports GET. Session params (URL, tutoring_type, focus_prompt) cannot be sent as a POST body. Use a two-step flow: (1) POST /sessions -> receive session_id, (2) GET /sessions/{id}/stream opens the EventSource. Alternatively, pass small params as query strings on a GET endpoint.

### Pattern 6: Tutoring Type System Prompt Injection

**What:** Each tutoring type maps to a persona string prepended to every agent's system prompt. Same content, different tone and complexity.

**When to use:** Agent instantiation at workflow build time

```python
# backend/app/agents/personas.py
PERSONAS = {
    "micro_learning": (
        "You are a concise tutor. Use short sentences, bullet points, and bold key terms. "
        "Every explanation must be under 2 sentences. No elaboration unless essential."
    ),
    "teaching_a_kid": (
        "You are explaining this to a curious 10-year-old. Use simple words, analogies to "
        "everyday things (toys, food, school), and an encouraging tone. Avoid jargon entirely."
    ),
    "advanced": (
        "You are a subject-matter expert tutoring a graduate student. Use precise terminology, "
        "assume university-level background, include nuance, caveats, and connections to broader concepts."
    ),
}
```

### Anti-Patterns to Avoid

- **Blocking the SSE event loop:** Agno's `workflow.run()` is a synchronous generator. Running it inside an async FastAPI handler without yielding control will queue all SSE frames and release them at once when the workflow completes. Always `await asyncio.sleep(0)` between sync yields.
- **Storing sessions via Agno's built-in DB in Phase 1:** Agno has PostgreSQL session storage built in. Do not wire it up for Phase 1 — use a plain Python dict. Avoids database infrastructure scope creep.
- **Treating OAT UI as a React component library:** OAT UI (oat.ink) is vanilla HTML/CSS with zero React dependencies. Import its CSS globally; do not expect React component exports. All interactive React components (quiz state machine, tab switcher, progress bar) must be plain React.
- **Assuming trafilatura always returns a string:** `trafilatura.extract()` returns `None` when extraction fails. Always check for `None` and length before treating the result as valid content.
- **Using Next.js API routes to proxy the SSE stream:** Known timeout limitations on Vercel (30 seconds). For this phase (local dev), this is fine; plan to route SSE directly from FastAPI in production.
- **Embedding full session data in the complete SSE event:** Session data (notes + flashcards + quiz) can be large (10KB+). Pass only `session_id` in the SSE complete event; deliver content via a separate GET /sessions/{id} REST endpoint.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSE event formatting (data: ...\n\n, retry, event type headers) | Custom StreamingResponse with manual string formatting | sse-starlette EventSourceResponse | W3C spec compliance, reconnection headers, event types, already battle-tested |
| Markdown rendering in React | innerHTML injection with AI output | react-markdown + remark-gfm | Safe by default (no XSS from AI output), handles GFM tables/lists, maps to custom components |
| Environment variable type coercion and validation | Manual os.environ.get() with string parsing | pydantic-settings BaseSettings | Type safety, .env file loading, validation errors at startup not runtime |
| URL -> plain text extraction | Custom BeautifulSoup scraper | Jina Reader + trafilatura chain | Readability heuristics are complex; trafilatura outperforms custom implementations in all benchmarks |

**Key insight:** URL content extraction looks simple but involves readability detection, boilerplate removal, JavaScript rendering, and encoding issues. The Jina -> trafilatura -> Playwright chain delegates each problem to a purpose-built tool. A custom scraper will fail on the exact sites users care most about.

---

## Common Pitfalls

### Pitfall 1: Agno Workflow Sync-Async Mismatch
**What goes wrong:** Calling synchronous `workflow.run()` inside an async FastAPI handler blocks the event loop. SSE frames queue up but never flush until the entire workflow completes — defeating the purpose of streaming.
**Why it happens:** Agno's core `Workflow.run()` is a synchronous generator. FastAPI runs on asyncio. Mixing sync generators into async code without proper bridging stalls the event loop.
**How to avoid:** Between each yielded `RunResponse`, call `await asyncio.sleep(0)` to yield control back to the event loop. Alternatively, check if Agno 2.5.x ships `arun()` for async workflows and use it natively.
**Warning signs:** Progress bar advances all at once when the workflow completes, not step-by-step.

### Pitfall 2: EventSource GET-Only Limitation
**What goes wrong:** Browser-native `EventSource` only supports GET requests. A form submission with URL, tutoring_type, and focus_prompt cannot be sent as a POST body.
**Why it happens:** The EventSource spec is GET-only by design. Many developers discover this only at integration time.
**How to avoid:** Use a two-step flow: (1) POST /sessions -> receive session_id, (2) GET /sessions/{id}/stream opens EventSource. The POST handles the body; the GET streams events.
**Warning signs:** 405 Method Not Allowed on the SSE endpoint, or CORS preflight failures.

### Pitfall 3: Jina Reader Empty Content for Valid Pages
**What goes wrong:** Jina Reader returns 200 with a short string ("This site requires JavaScript" or similar) for SPAs that require full rendering.
**Why it happens:** Jina Reader runs a headless browser but may not wait long enough for SPA hydration, or may extract from pre-render shell HTML.
**How to avoid:** Apply a content length threshold (minimum 200 characters) at each extraction layer before declaring success. Fall through to the next layer if the threshold is not met.
**Warning signs:** Notes and flashcards generated from a single sentence like "Please enable JavaScript to view this content."

### Pitfall 4: Playwright Cold Start Latency
**What goes wrong:** Playwright browser launch adds 2-5 seconds of cold start. If called frequently, the user experience suffers.
**Why it happens:** Chromium binary launch is inherently slow. Each call to `async_playwright()` starts a fresh browser process.
**How to avoid:** For Phase 1, cold start at layer 3 is acceptable — it only fires when Jina and trafilatura both fail. Do not pre-warm Playwright on server startup.
**Warning signs:** Sessions with JS-heavy pages consistently take 10+ seconds on the extraction step alone.

### Pitfall 5: OAT UI CSS Conflicts with React Components
**What goes wrong:** OAT UI styles native HTML elements directly by tag and semantic attribute (e.g., `button`, `input`, `[role="tab"]`). React components using these elements pick up unintended global styles.
**Why it happens:** OAT UI is class-free by design — it targets semantic HTML directly. This is its feature, not a bug, but it conflicts with component-library assumptions.
**How to avoid:** Scope OAT UI CSS to the root layout. Test each interactive component (tab switcher, quiz buttons, progress bar) early to see what OAT styles apply. Override with Tailwind utility classes or inline styles where conflicts occur.
**Warning signs:** Quiz answer buttons have unexpected hover or focus states from OAT UI's `button` styles.

### Pitfall 6: Agent Structured Output Parsing Failures
**What goes wrong:** Flashcards and quiz answers are returned as strings. JSON parsing fails when the model wraps output in prose or markdown code fences.
**Why it happens:** LLMs do not reliably return pure JSON without explicit prompt engineering.
**How to avoid:** Instruct each agent to "Return ONLY valid JSON, no markdown fences, no explanation." Wrap JSON parsing in a try/except; on failure, log the raw output and return an SSE error event.
**Warning signs:** Study page shows raw text strings instead of rendered flashcard or quiz components.

---

## Code Examples

### Jina Reader HTTP Request
```python
# Source: Jina Reader GitHub (github.com/jina-ai/reader)
async with httpx.AsyncClient(timeout=15) as client:
    resp = await client.get(
        f"https://r.jina.ai/{url}",
        headers={
            "Authorization": f"Bearer {settings.jina_api_key}",
            "X-Return-Format": "text",
        }
    )
content = resp.text.strip()
```

### trafilatura Extraction
```python
# Source: trafilatura docs (trafilatura.readthedocs.io/en/latest/quickstart.html)
downloaded = trafilatura.fetch_url(url)
if downloaded:
    text = trafilatura.extract(
        downloaded,
        include_tables=True,
        no_fallback=False,       # use backup algorithms for better coverage
        output_format="markdown" # preserve structure where possible
    )
    # text is None if extraction fails — always check before using
```

### pydantic-settings Config
```python
# Source: FastAPI docs (fastapi.tiangolo.com/advanced/settings)
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    agent_provider: str = "openai"
    agent_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""
    jina_api_key: str = ""
    allowed_origins: list[str] = ["http://localhost:3000"]

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

### react-markdown for Notes Panel
```typescript
// Source: react-markdown GitHub (github.com/remarkjs/react-markdown)
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function NotesPanel({ notes }: { notes: string }) {
  return (
    <article className="notes-content">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{notes}</ReactMarkdown>
    </article>
  );
}
```

### Agno Agent with Structured JSON Output
```python
# Source: Agno GitHub README (github.com/agno-agi/agno) + community patterns
from agno.agent import Agent
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS

def build_flashcard_agent(tutoring_type: str) -> Agent:
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="FlashcardAgent",
        model=get_model(),
        instructions=f"""{persona}

Generate flashcards from the provided study content.
Return ONLY a JSON array with no markdown fences, no explanation, no preamble.
Format exactly:
[
  {{"front": "Question text", "back": "Answer text"}},
  ...
]
Generate 8-12 flashcards covering the key concepts.""",
    )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pages Router API routes for SSE | App Router Route Handlers with ReadableStream | Next.js 13+ | Cleaner SSE; watch for 30s Vercel timeout on long generations |
| LangChain / LlamaIndex for agents | Agno and other lighter frameworks | 2024-2025 | Less abstraction overhead; Agno chosen per AGENT-01 |
| WebSockets for server-push progress | SSE via EventSource | 2024-2025 momentum | SSE simpler for unidirectional progress; no WebSocket handshake complexity |
| newspaper3k for extraction | trafilatura | 2022-2024 | trafilatura has higher benchmark accuracy across all comparison studies |
| Custom env parsing with os.environ | pydantic-settings v2 | Pydantic v2 release | Type-safe, validated settings with .env support out of the box |

**Deprecated/outdated:**
- `newspaper3k`: Last major release 2020; trafilatura outperforms it in all benchmarks. Do not use.
- `phidata`: Agno was previously named phidata. Older blog posts use this name; the code patterns are structurally similar but import paths have changed.
- Next.js Pages Router `/pages/api/*` for SSE: Known streaming issues; use App Router Route Handlers or route directly to FastAPI.

---

## Claude's Discretion: Recommendations

These areas were left to Claude's discretion in CONTEXT.md.

### Textarea Character Limits
- **Minimum:** 500 characters (~100 words) — below this, agents produce thin, low-quality output
- **Maximum:** 50,000 characters (~10,000 words) — above this, prompt overhead reduces effective generation quality for most models
- **UI hint:** Show a live character counter. Color amber below 500 (warn: too short), green 500-50000 (acceptable), red above 50000 (warn: too long).

### Garbled Text Handling
- **Recommendation:** Pass through to agents without hard client-side rejection. The agents will produce low-quality output for garbled text, which is its own feedback to the user.
- **Exception:** Reject client-side if the pasted text is shorter than 200 characters — return an inline error: "Please paste at least a few paragraphs of text for best results."

### Progress Bar Segment Widths
- 4 steps weighted toward generation (slower than extraction): extracting = 10%, notes = 40%, flashcards = 70%, quiz = 100%
- CSS transition: `transition: width 400ms ease-in-out` — smooth animated fill, not discrete jumps
- Do not pulse or animate beyond the fill animation — keep it calm and trustworthy

### Error Pointer Wording by Kind

| Kind | Top-level message | Specific pointer |
|------|------------------|-----------------|
| `paywall` | "We couldn't read that page" | "This looks like a paywalled article. Try pasting the article text below." |
| `invalid_url` | "We couldn't read that page" | "The URL doesn't look valid. Check it and try again, or paste the article text." |
| `empty` | "We couldn't read that page" | "The page loaded but didn't have enough readable text. You can paste the content below." |
| `unreachable` | "We couldn't reach that page" | "The site may be down or blocked. Paste the article text below to continue." |

---

## Open Questions

1. **Agno `RunEvent.running` enum value exists?**
   - What we know: `RunEvent.workflow_started` and `RunEvent.workflow_completed` are confirmed in Agno docs. Progress mid-workflow needs an intermediate event type.
   - What's unclear: Whether `RunEvent.running` exists in the 2.5.2 package.
   - Recommendation: On first implementation, inspect the enum: `from agno.run.response import RunEvent; print(list(RunEvent))`. If `running` does not exist, use `workflow_started` for all mid-workflow messages — the frontend reads `content`, not `event`.

2. **Agno `Workflow.arun()` async variant available?**
   - What we know: Agno advertises unified sync/async support. The `Agent` class has both `run()` and `arun()`.
   - What's unclear: Whether `Workflow` class exposes `arun()` in 2.5.2.
   - Recommendation: Check installed package (`help(Workflow)`) before building the SSE endpoint. If `arun()` exists, use it natively in async FastAPI without `run_in_executor`.

3. **Two-step vs query-string session creation**
   - What we know: EventSource is GET-only. Session params need to reach the backend.
   - What's unclear: Whether params (URL can be long) fit safely in a query string.
   - Recommendation: Use the two-step approach: POST /sessions (JSON body) -> receive `{session_id}` -> EventSource GET /sessions/{session_id}/stream. Cleaner, no query string length concerns.

4. **Jina Reader current free tier limits**
   - What we know: Historically 10M free tokens; 100 RPM free; new pricing model introduced May 2025.
   - What's unclear: Whether the May 2025 pricing change affects free tier limits for new keys.
   - Recommendation: Create a Jina API key before building the extraction chain and verify the dashboard shows current limits. Make Jina optional — if `JINA_API_KEY` is empty, skip layer 1 and fall directly to trafilatura.

---

## Sources

### Primary (HIGH confidence)
- Agno PyPI (pypi.org/project/agno) — version 2.5.2 confirmed, February 15, 2026 release
- Agno GitHub README (github.com/agno-agi/agno) — agent/workflow patterns, model provider imports confirmed
- Agno Docs: Workflows Running (docs.agno.com/basics/workflows/running-workflows) — event types, streaming API, stream_events parameter
- sse-starlette PyPI (pypi.org/project/sse-starlette) — version 3.2.0, EventSourceResponse, JSONServerSentEvent API
- trafilatura Docs (trafilatura.readthedocs.io/en/latest/quickstart.html) — fetch_url, extract functions
- FastAPI Docs: Settings (fastapi.tiangolo.com/advanced/settings) — pydantic-settings pattern
- FastAPI Docs: CORS (fastapi.tiangolo.com/tutorial/cors) — CORSMiddleware
- Jina Reader GitHub (github.com/jina-ai/reader) — API usage, headers, response format
- react-markdown GitHub (github.com/remarkjs/react-markdown) — React markdown rendering
- Playwright Python Docs (playwright.dev/python/docs/pages) — page.content(), async usage

### Secondary (MEDIUM confidence)
- Agno Workflows Introduction — workflow class pattern, sequential steps, RunResponse/RunEvent confirmed
- bitdoze.com Agno Workflow article — confirmed Workflow class + run() generator pattern in practice
- Upstash Blog: SSE streaming in Next.js (upstash.com/blog/sse-streaming-llm-responses) — EventSource + useState + useEffect pattern
- Pedro Alonso Blog: SSE in Next.js (pedroalonso.net/blog/sse-nextjs-real-time-notifications) — addEventListener named events pattern confirmed
- Agno model switching (agno.com blog) — "change openai:gpt-4o to groq:llama-3.3-70b-versatile" swappability confirmed

### Tertiary (LOW confidence — validate before using)
- `RunEvent.running` as a mid-workflow event type: inferred from community patterns, not verified against enum
- `_classify_failure()` domain-based paywall detection heuristic: training knowledge, not Jina documentation
- Agno `Workflow.arun()` async method availability: mentioned in marketing copy, not confirmed in API docs
- Content length threshold of 200 characters for valid extraction: reasonable heuristic, not benchmarked against production data

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified via PyPI, official docs, or GitHub READMEs with current versions
- Architecture patterns: MEDIUM-HIGH — patterns verified via docs and community articles; Agno mid-workflow event names need validation against installed package
- Pitfalls: MEDIUM — extraction pitfalls are well-documented; Agno sync/async pitfall inferred from framework design but confirmed by EventSource pattern being GET-only (HIGH on that specific point)
- OAT UI as non-React library: HIGH — confirmed from oat.ink: "zero dependencies", "HTML + CSS", "no framework"

**Research date:** 2026-02-18
**Valid until:** 2026-03-18 (30 days — stable libraries; Agno is actively developed and may ship minor API changes)
