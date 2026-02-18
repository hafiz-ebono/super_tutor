# Pitfalls Research

**Domain:** AI tutoring / LLM-powered ed-tech web app
**Researched:** 2026-02-18
**Confidence:** MEDIUM — WebSearch and WebFetch were unavailable. Findings are drawn from known engineering patterns, published AI/education research, and LLM deployment post-mortems from training data (cutoff August 2025). Flag for validation before final roadmap lock.

---

## Critical Pitfalls

### Pitfall 1: Confident Hallucination in Educational Content

**What goes wrong:**
The LLM generates factually incorrect notes, flashcard answers, or quiz explanations — but presents them with high confidence and well-structured formatting. Because the output looks authoritative, users (especially learners) accept the errors without question. This is uniquely dangerous in an educational context where incorrect learning is worse than no learning.

**Why it happens:**
LLMs optimise for fluency and coherence, not factual accuracy. When asked to summarise a topic, the model will fill gaps in its training data with plausible-sounding fabrications. For niche technical topics, recent events, or subject-specific jargon, hallucination rates increase significantly. Structured output formats (flashcards, bullet notes) encourage the model to produce a "complete" set even when it doesn't have enough grounded information.

**How to avoid:**
- Ground all generation in the source material: pass the scraped article/URL content as the authoritative context, and instruct the model to only generate claims that are directly supported by that content.
- For topic-description mode (no URL provided), make the sourcing limitation explicit in the UI: "Content generated from AI knowledge — verify with primary sources."
- Add a system prompt instruction: "If you cannot find evidence for a claim in the provided content, say so rather than inferring." Do not ask the model to "fill gaps."
- For quiz answer explanations, require the model to cite the specific section of the notes it drew from.
- Run a self-consistency check: generate notes, then ask the model to flag any claims in the notes it cannot directly support from the source text.

**Warning signs:**
- Quiz explanations reference facts not present in the scraped article.
- Notes contain dates, statistics, or named entities that appear nowhere in the source URL.
- Flashcard "answers" are longer and more elaborate than the source material warrants.
- Testing with a known-bad or stub article still produces confident, detailed notes.

**Phase to address:** Session Generation MVP (core generation pipeline). Do not defer — hallucination in structured output is load-bearing for the product's credibility.

---

### Pitfall 2: Web Scraping Brittleness Treated as a Solved Problem

**What goes wrong:**
URL-based sessions fail silently or return garbage content for a large class of real-world URLs. JavaScript-rendered pages, paywalled articles, login-gated content, and aggressive bot-protection (Cloudflare, DataDome) all return either empty content, boilerplate error HTML, or partial navigation chrome rather than the article body. The AI then generates notes from the wrong content — or the backend crashes without a user-friendly error.

**Why it happens:**
Simple HTTP `requests` + BeautifulSoup scraping works on ~40-60% of real URLs but fails on the rest. Developers test with simple static pages (Wikipedia, plain blogs) during development, don't discover the failure modes until users submit real URLs.

**How to avoid:**
- Use a headless browser layer (Playwright) for JS-heavy sites rather than plain HTTP fetching.
- Integrate a dedicated extraction service (Jina AI Reader at `r.jina.ai/{url}`, Firecrawl, or similar) that handles JS rendering and returns clean markdown — these handle far more of the URL surface than DIY scraping.
- Implement content validation before sending to the LLM: check that extracted text length is above a minimum threshold (e.g., 500 words) and does not match known paywall/login page signatures.
- Return a clear error to the user when extraction fails: "We couldn't extract readable content from this URL. Try pasting the article text directly." — offer a text-paste fallback.
- Do not silently generate from boilerplate navigation HTML. Always validate content quality before generation.

**Warning signs:**
- Scraped content contains navigation menus, cookie consent text, or "Subscribe to read" copy.
- Extraction returns under 200 words for a URL that should contain a long-form article.
- Notes generated from a paywalled URL reference subscription plans or login prompts.
- Testing with Medium, Substack, or NYT URLs causes backend errors or empty generation.

**Phase to address:** URL ingestion / content extraction phase. Must be addressed before any user testing with real URLs.

---

### Pitfall 3: Blocking the User During Long AI Generation (No Streaming / No Progress Feedback)

**What goes wrong:**
Session creation — scraping a URL, generating notes, flashcards, and a quiz in a single LLM call — can take 30-90 seconds. If the frontend shows a simple spinner with no progress indication, users assume it crashed and refresh or abandon the session. Refreshing kills the ephemeral session entirely since there is no persistence.

**Why it happens:**
Developers test locally where LLM latency is masked by fast network connections and small test payloads. Generation pipelines are built as single blocking calls before thinking about UX. SSE or WebSocket streaming feels like added complexity and gets deferred.

**How to avoid:**
- Use streaming responses (SSE from FastAPI or WebSocket) and render notes progressively as they arrive — the user sees content appearing rather than waiting for a complete response.
- If full streaming is not in scope for v1, use a multi-step generation with discrete progress events: "Extracting content (1/4)... Generating notes (2/4)... Creating flashcards (3/4)... Building quiz (4/4)..."
- Set a realistic timeout and fail gracefully with a user-visible error message rather than a silent hang.
- Consider breaking generation into sequential API calls (notes first, then flashcards, then quiz) and revealing each section as it completes — even without streaming, this reduces perceived wait time dramatically.
- Do not generate all three artifacts (notes + flashcards + quiz) in a single prompt — this maximises latency and creates a single point of failure.

**Warning signs:**
- A test session with a 3,000-word article takes more than 45 seconds end-to-end with no UI feedback.
- Users in testing say they refreshed because they thought it hung.
- The backend has no timeout configured on the generation endpoints.
- Generation is a single `await llm.generate(giant_prompt)` call.

**Phase to address:** Session generation pipeline + frontend UX. Must be addressed before any user-facing release.

---

### Pitfall 4: In-Session Chat Loses Context or Answers Outside the Study Material

**What goes wrong:**
The in-session AI chat either: (a) forgets the session content when the conversation grows long and starts hallucinating answers unrelated to the article, or (b) answers any question the user asks regardless of relevance, turning the tutor into a general-purpose chatbot rather than a focused learning assistant.

**Why it happens:**
(a) Context window pressure: naively concatenating the full article + notes + full chat history quickly exceeds practical context limits, causing the model to lose grip of the source material. (b) Absent system prompt constraints: without explicit instructions to stay within the session material, the model will answer general questions because it is trained to be helpful.

**How to avoid:**
- Implement a lightweight RAG pattern for the chat: chunk the session notes and article into segments, embed them, and retrieve the top-N relevant chunks per user question rather than always including the entire source.
- Always include the session notes (not the raw article) in the system context for chat — notes are already compressed summaries, reducing token pressure while maintaining coverage.
- Add an explicit system prompt instruction: "You are a tutor helping the user understand this specific material. Only answer questions based on the study session content. If the user asks something outside this material, say 'That's outside our study material — let's stay focused on [topic].'"
- Cap the chat history included in context: include last N turns (e.g., 6-10) plus the full system context, not the entire conversation.
- Do not give the chat bot access to the raw full-text article on every turn — this is expensive and often exceeds context.

**Warning signs:**
- After 10+ chat turns, the AI starts giving answers that contradict the original notes.
- The AI answers "What is the capital of France?" when the session is about React hooks.
- Chat responses reference information clearly not in the session material.
- API token counts per chat turn are unexpectedly high (raw article being sent every time).

**Phase to address:** In-session chat implementation phase. RAG/chunking design must be planned before first chat implementation, not retrofitted.

---

### Pitfall 5: Trivial or Misleading Quiz Questions

**What goes wrong:**
The auto-generated quiz contains questions that are either: (a) too shallow ("What is the title of the article?"), (b) ambiguous where multiple answers could be correct, (c) have trick-question distractors that are misleading rather than educational, or (d) test vocabulary over understanding. Users complete the quiz but learn nothing, and the session feels low-quality.

**Why it happens:**
LLMs default to surface-level question generation unless heavily prompted. Without explicit Bloom's taxonomy targeting or difficulty constraints, the model generates the easiest questions to write — definition recall. Distractor generation is particularly weak: models often produce obviously wrong distractors that make the correct answer trivially obvious.

**How to avoid:**
- In the quiz generation prompt, specify question types by tutoring mode: Micro Learning → application questions ("Given X, what would happen if..."), Teaching a Kid → conceptual questions with analogies, Advanced → analysis and synthesis questions.
- Explicitly forbid trivial question patterns in the prompt: "Do not ask about titles, author names, or definitions that are stated verbatim in the text. Questions must test understanding, not memorisation of exact phrases."
- For distractors: prompt the model to generate distractors that are "plausible to someone who partially understands the topic" not "obviously wrong." Specify that all options should be the same length and grammatical structure to avoid giveaway formatting cues.
- Include a validation step: after generating the quiz, run a second prompt that reviews each question for ambiguity and flags questions where more than one answer could be argued as correct.
- Minimum bar: 4 answer options per question, no "all of the above" or "none of the above."

**Warning signs:**
- More than 30% of quiz questions start with "What is defined as..." or "According to the article..."
- Users score 100% on the quiz but still say the session felt unhelpful.
- Quiz questions reference content verbatim rather than paraphrasing it.
- All distractors are obviously wrong on first read.

**Phase to address:** Quiz generation prompt engineering phase. Must be validated with human review of generated quizzes before shipping.

---

### Pitfall 6: Context Window Overflow on Long Articles

**What goes wrong:**
A user submits a long-form article (10,000+ words, full technical documentation page, or a multi-section guide), the full content is passed to the LLM, and either: (a) the generation silently degrades because the model loses coherence on content near the middle/end of the context, or (b) the API call fails with a context limit error that crashes the session.

**Why it happens:**
Developers test with short articles during development. The "works fine" assumption is built on 500-2,000 word test cases. Long content is an edge case that only surfaces when real users test real URLs.

**How to avoid:**
- Implement content truncation with a hard ceiling before sending to the LLM: cap input at a sensible limit (e.g., 8,000-12,000 tokens depending on the model). Truncate at a natural paragraph boundary, not mid-sentence.
- For very long articles, implement extractive summarisation first: chunk the article into sections, summarise each section independently, then concatenate the section summaries as the LLM input for note/flashcard/quiz generation.
- Inform the user when content has been truncated: "This article is very long. We focused on the first X sections — consider providing a more specific URL or focus prompt."
- Use the `focus_prompt` field to guide what portions to prioritise when content must be trimmed.
- Track token counts before generation calls, not after — fail fast with a clear error rather than letting an oversized prompt silently degrade quality.

**Warning signs:**
- Notes generated from a 15,000-word documentation page are the same depth as notes from a 1,000-word article — the model is ignoring most of the content.
- API errors with `context_length_exceeded` appearing in backend logs for certain URLs.
- Notes from long articles are noticeably more generic and less specific than notes from short articles.
- The last sections of a long article are never represented in notes or quiz questions.

**Phase to address:** Content ingestion and pre-processing phase. Token budgeting must be designed into the prompt pipeline, not added later.

---

### Pitfall 7: Tutoring Mode Has No Real Effect on Output

**What goes wrong:**
The three tutoring modes (Micro Learning, Teaching a Kid, Advanced) produce nearly identical output because the prompt differences are superficial. "Teaching a Kid" uses the same vocabulary and sentence structure as "Advanced." Users select a mode but perceive no meaningful difference, making the mode selector feel like a decoration rather than a feature.

**Why it happens:**
Developers add mode-switching logic that passes a single label ("You are tutoring a child") to the system prompt without specifying what that actually means in terms of vocabulary, examples, analogies, depth, and format. The model interprets the instruction weakly.

**How to avoid:**
- Define each mode as a detailed persona specification, not a label: for each mode, specify reading level (Flesch-Kincaid target), use of analogies (required/optional/avoid), technical jargon policy, note structure (bullets vs. paragraphs vs. numbered steps), flashcard question type, and quiz question style.
- Example: "Teaching a Kid mode: Use vocabulary a 10-year-old would know. Explain every concept with a real-world analogy. Keep sentences under 15 words. Flashcard answers should be one sentence. Quiz questions should test 'what does X do' not 'what is the technical term for X.'"
- After implementation, test the same URL across all three modes and compare outputs side-by-side. If an untrained reviewer cannot distinguish the modes, the prompts need more specificity.
- Consider structural differences beyond tone: Micro Learning = bullet summary + 5 flashcards + 3 quiz questions; Advanced = concept map structure + 10 flashcards with nuance + 5 quiz questions requiring synthesis.

**Warning signs:**
- A technical programming article in "Teaching a Kid" mode uses terms like "asynchronous," "callback," and "event loop" without explanation or analogy.
- Flashcards across modes have the same length and format.
- Users report all three modes feel "the same."

**Phase to address:** Prompt engineering / session generation phase. Define mode specifications before writing prompts, not after.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single giant prompt (notes + flashcards + quiz in one call) | Faster to implement | Single point of failure; max latency; no progressive reveal; hard to debug quality issues per artifact type | Never — break into separate calls from day one |
| Raw article as chat context (no RAG/chunking) | Simple implementation | Token costs balloon; coherence degrades after 5+ turns; model loses track of source material | MVP only if article is short (<2k words) and chat is lightly used |
| No content validation after scraping | Faster ingestion pipeline | Silent bad generations from navigation HTML, paywall pages, or empty content | Never — always gate on minimum content quality |
| No token counting before LLM calls | Simpler code | Random crashes on long articles; degraded quality on oversized inputs with no visibility | Never — token budgeting is infrastructure, not optimization |
| Hardcoded prompts with no mode differentiation | Faster MVP | Mode selector is a UI lie; user trust collapses when they notice | Never if modes are exposed in UI |
| No streaming, full wait before render | Simpler frontend | Users abandon sessions; ephemeral state means no recovery after refresh | Acceptable only for internal testing, never for user-facing |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OpenAI / Anthropic API | Not handling rate limit (429) errors gracefully — backend throws 500 to frontend | Implement exponential backoff with jitter; surface "AI service busy, retrying..." to user |
| OpenAI / Anthropic API | Using `max_tokens` too low and getting truncated responses mid-JSON or mid-sentence | Set `max_tokens` well above expected output size; validate response completeness before parsing |
| URL scraping (any library) | Not setting a User-Agent header — many sites block the default Python requests UA | Set a realistic browser User-Agent string on all HTTP requests |
| URL scraping | Not handling redirect chains, meta-refresh, or canonical URL mismatches | Follow redirects; validate that the final URL matches the intended content domain |
| Jina Reader / Firecrawl | Assuming 100% success rate — services have their own rate limits and failure modes | Implement fallback: Jina → Playwright → error with paste-text fallback |
| LLM structured output (JSON mode) | Parsing raw JSON from model response without validation — model occasionally generates invalid JSON even in JSON mode | Always validate and catch JSON parse errors; have a retry-with-cleaner-prompt fallback |
| FastAPI streaming (SSE) | Not setting correct MIME type (`text/event-stream`) and not disabling response buffering | Set `Content-Type: text/event-stream`, `Cache-Control: no-cache`, and `X-Accel-Buffering: no` on SSE endpoints |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Sequential generation (notes, then flashcards, then quiz, each blocking the next) | 60-120 second session creation time | Generate notes first (user reads while waiting), then fire flashcard + quiz generation in parallel | Immediately on any article >1,000 words |
| Embedding full article on every chat turn | Chat API costs 10x higher than expected; slow response times | Embed article once at session creation, cache embeddings in memory for session lifetime | After ~5 chat turns |
| Scraping without timeout | Slow URLs hang the backend indefinitely — no response to frontend | Set aggressive HTTP timeouts (10s connect, 30s read); always return to user within 60s | Any URL with a slow server or redirect loop |
| Re-fetching URL content on every generation step | Doubled scraping time; risk of getting different content on second fetch | Scrape once, cache content in session state for all downstream generation steps | Every session with URL input |
| No session-level caching of generated content | Same URL + same focus prompt regenerates from scratch on every request | Cache generated session content by hash(url + focus_prompt + mode) in memory with TTL | At any meaningful usage level |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Passing user-supplied URLs directly to scraping library without validation | SSRF (Server-Side Request Forgery): users can probe internal services (e.g., `http://localhost:8080/admin`, `http://169.254.169.254/`) | Validate URL scheme (https only), resolve hostname to IP and block private/RFC1918 ranges before fetching |
| Including raw user focus_prompt verbatim in system prompt without sanitisation | Prompt injection: user can override system instructions and extract system prompt or generate harmful content | Sanitise user input: strip control characters, wrap user content in clear delimiters in the prompt (`<user_input>...</user_input>`), and instruct model to treat it as data not instructions |
| Trusting scraped content as safe HTML to render | XSS if scraped content is rendered as HTML in the frontend | Always render notes/flashcards/quiz as plain text or properly sanitised markdown — never `innerHTML` from LLM or scraped output |
| No rate limiting on generation endpoints | A single user can exhaust OpenAI API budget in minutes | Rate limit session creation endpoint per IP (e.g., 10 sessions per hour per IP) even without user auth |
| Logging full scraped article content | PII exposure if user scrapes a page containing personal data | Log only URL, content length, and status — not raw content |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No feedback during generation (blank screen or static spinner) | Users think it crashed and refresh, destroying the ephemeral session | Multi-step progress: show each stage completing as it happens |
| Notes rendered as a wall of text | Users don't know where to start; skips learning benefit | Enforce structured note format: H2 sections, bullet points under each, bold key terms |
| Flashcards in random order every time | Users cannot track which cards they've reviewed | Maintain card order within a session; allow "flip all" and "mark as known" interactions |
| Quiz shows answer immediately on selection | Users guess-and-check without thinking | Require confirmation ("Submit answer") before revealing result |
| No way to copy or export notes | Users lose content when they close the tab (ephemeral sessions have no persistence) | Add a "Copy all notes" button and "Download as PDF" — low effort, high retention value |
| Tutoring mode selected after content is generated | Users don't understand that mode affects content, not display | Make mode selection happen before session creation; lock it after generation starts |
| Generic "Something went wrong" errors | Users don't know if it was a bad URL, a timeout, or an AI failure | Return specific, actionable errors: "This URL is behind a paywall," "Generation timed out — try a shorter article," "Invalid URL format" |

---

## "Looks Done But Isn't" Checklist

- [ ] **URL ingestion:** Passes testing on Wikipedia and plain blogs — verify with Medium, Substack, NYT (paywall), a JS-heavy docs site (e.g., Stripe docs), and a GitHub README
- [ ] **Notes quality:** Output looks well-formatted — verify that content is grounded in the source article and not fabricated by testing with a deliberately narrow/niche article
- [ ] **Flashcards:** Cards are generated — verify that Q and A are not copies of the same text, and that answers are not longer than the question warrants
- [ ] **Quiz:** 4 questions appear — verify that questions are not trivially answered by copying verbatim from notes, and that distractors are plausible
- [ ] **Tutoring modes:** Selector changes output visibly — verify by running the same article through all three modes and comparing word count, vocabulary complexity, and question depth
- [ ] **In-session chat:** Chat responds correctly on turn 1 — verify after 15 turns that responses are still grounded in session material and not drifting
- [ ] **Long article handling:** Works on 1,000-word article — verify with a 10,000-word documentation page; check that generation does not silently truncate or degrade
- [ ] **Error states:** Happy path works — verify error messages for: invalid URL, paywalled URL, empty/no-content URL, LLM timeout, LLM rate limit
- [ ] **Streaming/progress:** Generation starts — verify what a user sees if they are on a slow connection or if generation takes 60+ seconds

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hallucination discovered post-launch | HIGH | Add grounding instructions to all generation prompts (redeploy); add "AI-generated — verify with sources" disclaimer to all content; consider adding a "Report error" button |
| Scraping failures across many URL types | MEDIUM | Swap scraping library for Jina Reader / Firecrawl (API integration, not rewrite); add paste-text fallback path |
| No streaming causing user abandonment | MEDIUM | Add SSE streaming to generation endpoints; requires frontend changes to render partial content |
| Chat context drift causing bad answers | MEDIUM | Add RAG chunking layer to chat; requires embedding infrastructure (can use lightweight in-memory solution) |
| Quiz quality complaints | LOW | Iterate on quiz generation prompt only — no infrastructure changes needed |
| Context window errors on long articles | LOW | Add token counting and truncation to ingestion pipeline — localised change |
| Modes feel identical | LOW | Rewrite mode-specific prompt sections — no infrastructure changes needed |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Hallucination in educational content | Phase 1: Session generation pipeline | Run generation against 5 test articles; manually verify all factual claims against source |
| Web scraping brittleness | Phase 1: URL ingestion | Test against 10 diverse URL types including paywalls, JS-heavy sites, and redirect chains |
| Long generation wait with no feedback | Phase 1-2: Generation pipeline + Frontend UX | Measure end-to-end time on a 5,000-word article; must show progress events within 3 seconds of submission |
| Chat context drift and scope bleed | Phase 2: In-session chat | Run 20-turn chat session; verify all answers are traceable to session material |
| Trivial/misleading quiz questions | Phase 1: Quiz generation prompts | Human review of 20 generated quizzes across all 3 modes and article types |
| Context window overflow | Phase 1: Content ingestion | Test with articles of 2k, 5k, 10k, and 20k words; verify graceful handling at each tier |
| Tutoring mode has no real effect | Phase 1: Prompt engineering | Side-by-side comparison of all 3 modes on identical input by a reviewer blind to which mode was used |
| SSRF via user-supplied URLs | Phase 1: URL ingestion security | Attempt to fetch `http://localhost`, `http://169.254.169.254`, and private IP ranges; must be blocked |
| Prompt injection via focus prompt | Phase 1: Input sanitisation | Attempt "Ignore previous instructions and..." in focus prompt; verify system prompt is not extracted |
| No rate limiting on generation | Phase 2: API hardening | Verify 429 is returned after threshold; verify API costs do not spike from a single user |

---

## Sources

- Training knowledge: LLM deployment post-mortems and engineering blog patterns (Anthropic, OpenAI, Hugging Face community discussions) — MEDIUM confidence
- AI in education research synthesis: Known patterns from academic literature on AI tutoring systems (ITS, cognitive tutors), Stanford HAI publications, MIT CSAIL ed-tech research — MEDIUM confidence
- Web scraping reliability: Known failure modes documented across Python scraping ecosystem (requests, BeautifulSoup, Playwright, Scrapy communities) — HIGH confidence (stable, well-documented problem space)
- LLM context window degradation: Known "lost in the middle" finding (Liu et al., 2023) — HIGH confidence (published and replicated)
- Prompt injection and SSRF: OWASP LLM Top 10 (2024 version) — HIGH confidence
- FastAPI SSE patterns: Known implementation requirements — MEDIUM confidence

*Note: WebSearch and WebFetch were unavailable during this research session. Findings reflect training knowledge up to August 2025. Recommend validating the specific tools section (Jina Reader, Firecrawl availability and pricing) against current sources before implementation.*

---
*Pitfalls research for: AI tutoring / LLM-powered ed-tech web app (Super Tutor)*
*Researched: 2026-02-18*
