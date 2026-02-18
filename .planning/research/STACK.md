# Stack Research

**Domain:** AI Tutoring / Ed-Tech Web App (Super Tutor)
**Researched:** 2026-02-18
**Confidence:** MEDIUM — Based on training data through August 2025. Library versions are correct as of mid-2025; verify on PyPI before installing.

---

## Pre-decided Stack Constraints

| Layer | Decision | Rationale |
|-------|----------|-----------|
| Frontend UI | OAT UI (oat.ink) | Developer preference |
| Backend framework | FastAPI (Python) | Developer preference |
| Session persistence | None in v1 | Ephemeral sessions, no user accounts |

---

## Recommended Stack

### Backend Core

| Package | Version | Purpose | Confidence |
|---------|---------|---------|-----------|
| `fastapi` | `^0.115` | Async web framework, SSE, OpenAPI docs | HIGH |
| `uvicorn[standard]` | `^0.34` | ASGI server with uvloop | HIGH |
| `pydantic` | `^2.9` | Validation + structured LLM output parsing | HIGH |
| `python-dotenv` | `^1.0` | API key management | HIGH |

### LLM Integration

| Package | Version | Purpose | Confidence |
|---------|---------|---------|-----------|
| `openai` | `^1.57` | Primary LLM SDK — GPT-4o + GPT-4o-mini | HIGH |
| `anthropic` | `^0.40` | Alternative SDK — Claude 3.5 Sonnet swap-in | HIGH |

**Model recommendations:**
- Session generation: `gpt-4o` — best structured JSON output reliability
- In-session chat: `gpt-4o-mini` — faster, cheaper for conversational turns
- Topic research synthesis: `gpt-4o`

**NOT:** LangChain, LlamaIndex (abstraction overhead for a project that does not need a vector pipeline), local LLMs (latency/quality), Azure OpenAI (auth complexity).

### URL Content Extraction

| Service/Package | Version | Purpose | Confidence |
|---------|---------|---------|-----------|
| Jina AI Reader | via `httpx` GET `r.jina.ai/{url}` | Managed extraction — handles JS-rendered pages, returns clean markdown, no SDK | MEDIUM |
| `trafilatura` | `^2.0` | DIY fallback article extractor | HIGH |
| `httpx` | `^0.28` | Async HTTP client | HIGH |
| `playwright` | `^1.49` | Headless browser last-resort fallback | MEDIUM |

**Extraction chain:** Jina Reader → trafilatura → Playwright → error with paste-text fallback

**NOT:** `requests` (synchronous, blocks event loop), BeautifulSoup alone (no article-vs-navigation concept), Scrapy (crawl framework overkill), Selenium (slower than Playwright).

### Web Research (Topic Path)

| Service | Package | Purpose | Confidence |
|---------|---------|---------|-----------|
| Tavily | `tavily-python ^0.5` | Search + content extraction in one call; LLM-pipeline native | MEDIUM |

**NOT:** Serper/SerpAPI (returns URLs only, requires separate fetch per result), DuckDuckGo unofficial API (unstable), Perplexity API (too expensive inside a pipeline step).

### In-Session RAG Chat

**Decision: Context-stuffing (NOT a vector database)**

Session content (notes + flashcards + quiz) is 1,000–4,000 tokens. GPT-4o has a 128k context window. No retrieval problem exists. Inject session content into the chat system prompt directly.

**NOT:** ChromaDB, Pinecone, Weaviate, FAISS, pgvector — these solve retrieval across large corpora or across sessions. Neither applies in v1.

### Frontend Additions

| Package | Version | Purpose | Confidence |
|---------|---------|---------|-----------|
| `marked` | `^15.0` | Markdown → HTML for notes display | HIGH |
| `dompurify` | `^3.2` | XSS sanitisation before innerHTML injection | HIGH |

### Dev Tooling

| Tool | Version | Purpose |
|------|---------|---------|
| `ruff` | `^0.9` | Lint + format (replaces flake8 + black + isort) |
| `pytest` | `^8.3` | Test runner |
| `pytest-asyncio` | `^0.25` | Async test support |

---

## Consolidated Dependencies

**`requirements.txt`:**
```
fastapi>=0.115,<1.0
uvicorn[standard]>=0.34,<1.0
pydantic>=2.9,<3.0
python-dotenv>=1.0,<2.0
openai>=1.57,<2.0
anthropic>=0.40,<1.0
httpx>=0.28,<1.0
trafilatura>=2.0,<3.0
playwright>=1.49,<2.0
tavily-python>=0.5,<1.0
ruff>=0.9
pytest>=8.3
pytest-asyncio>=0.25
```

**`package.json` additions:**
```json
{ "dependencies": { "marked": "^15.0.0", "dompurify": "^3.2.0" } }
```

---

## What NOT to Need in v1

- Redis — only for shareable session links (v1.x) or URL caching at scale
- Celery/ARQ — SSE streaming handles UX; add queue only if >60s generation becomes a problem
- Any database — zero persistence by design
- Docker Compose complexity — single FastAPI Dockerfile is sufficient
