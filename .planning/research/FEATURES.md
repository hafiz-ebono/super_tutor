# Feature Research

**Domain:** AI Tutoring / Ed-Tech Web App
**Researched:** 2026-02-18
**Confidence:** MEDIUM — Based on training data through mid-2025 covering major AI tutoring products (Khanmigo, Quizlet Q-Chat, Socratic, Photomath, StudyFetch, Notion AI, ChatGPT Edu). WebSearch and WebFetch unavailable; findings rely on training data. Core feature claims are HIGH confidence (stable market patterns); pricing/feature specifics for competitors are MEDIUM.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Content ingestion (URL or text) | Every AI study tool accepts input; feels broken without it | LOW | URL scraping has edge cases (paywalls, JS-heavy SPAs, bot blocks); plain text fallback reduces failure surface |
| Structured notes / summary | Core deliverable — why users come to a study app | MEDIUM | Quality determines whether users trust the product; length/depth calibration matters |
| Flashcards | Spaced repetition is the dominant study technique; users expect it from any study tool | MEDIUM | Format is simple; the challenge is generating high-signal cards (not trivially obvious ones) |
| Quiz / assessment | Self-testing is table stakes for active recall; any "study" product without it feels passive | MEDIUM | Multiple choice is the easiest format to generate reliably and grade automatically |
| In-session AI chat | Post-ChatGPT, users expect to be able to ask follow-ups in any AI product | MEDIUM | Context management (chat must know session content) is the real complexity |
| Responsive / readable UI | Learners use laptops; content must be readable and scannable | LOW | Dense walls of text kill engagement; formatting and spacing matter as much as content |
| Fast generation feedback | Users abandon if they wait silently >10 seconds with no feedback | LOW | Streaming or progress indicators; not a feature but a UX requirement for any async AI app |
| Error handling for bad inputs | Users will enter paywalled URLs, broken links, or vague topics | LOW | Graceful degradation; clear error messages; this is repeatedly where ed-tech apps fail quietly |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but create meaningful competitive separation.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Tutoring type / tone adaptation (Micro / Kid / Advanced) | Rare — most AI study tools use a single register. Personalizing complexity and tone addresses diverse user mental models | LOW-MEDIUM | Super Tutor already plans this. Implementation complexity is in prompt engineering + validation; structural code is simple |
| URL + focus prompt combination | Most tools either ingest a whole URL or let the user ask a question. Letting users direct *which aspect* of an article to study is more powerful | LOW | The focus prompt shapes scope; this is differentiated and technically simple |
| Deep topic research mode (AI-researched) | Lets users start from scratch on any topic without needing a source. Expands addressable use cases to "I want to learn X from scratch" | HIGH | This is the hardest input path: needs web research, synthesis, hallucination risk is higher. Requires quality guardrails |
| Single-page session design | Many tools fragment the experience across multiple screens or sessions. Everything on one page reduces context switching | LOW | UX decision more than technical; reduces friction, aids flow state |
| Zero-friction start (no account) | Accounts are the #1 drop-off point for new users in ed-tech. Ephemeral sessions let users evaluate immediately | LOW | Already planned. Risk is that users can't return to sessions; worth flagging if retention becomes a goal later |
| Flashcard flip interaction | Obvious-seeming but many web-based flashcard tools have poor UX. A smooth, keyboard-navigable flip interaction raises perceived quality | LOW | Not complex; has outsized impact on UX perception |
| Quiz immediate feedback with explanations | Most AI quizzes just mark correct/wrong. Showing *why* an answer is correct ties back to the notes and builds understanding | MEDIUM | Requires AI to generate both answer options and explanations at generation time; adds to prompt complexity |
| Session shareable via link | Even without accounts, a session URL lets users share with classmates or revisit via bookmarks | LOW-MEDIUM | Requires ephemeral storage on server side (e.g., Redis with TTL); not full persistence |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem valuable but create more problems than they solve at this stage.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| User accounts / auth in v1 | Users ask for "save my sessions" early | Auth adds 2-4 weeks of infrastructure work, onboarding friction, email verification, password reset, GDPR considerations. Kills experimentation velocity | Defer to v2. Use shareable session links (ephemeral server storage with TTL) to partially address the save use case |
| Video / YouTube URL ingestion | YouTube is where a lot of learning happens | Transcription pipeline (Whisper or YouTube API) is a separate, complex integration. Transcripts are noisy. Changes the content extraction architecture significantly | Ship URL+text only; validate demand before building video support |
| Spaced repetition scheduling | SRS (Anki-style) is the gold standard for retention | Requires user accounts (needs to track review history), scheduling logic, and a reason to return daily. Cannot be built without persistence | Focus on in-session review quality; add SRS only after account system exists |
| Export to PDF / Anki / Notion | Power users request export constantly | Adds format-specific complexity for low-frequency actions. Anki format in particular has its own quirks | Add copy-to-clipboard for flashcards; defer structured export |
| Social / community features | "Study with friends" or shared decks | Adds moderation burden, real-time infra, identity complexity; none of this is core to the learning value | Pure solo tool in v1; consider optional sharing in v2 |
| Gamification (streaks, XP, badges) | Duolingo proved gamification drives engagement | Gamification without persistence is meaningless (no account = no streak). Also risks becoming a distraction from building core quality | Focus on intrinsic motivation — good content quality is the retention driver |
| True/false and short-answer quiz formats | Users ask for variety | Each format requires a different generation prompt, different grading logic, different UI. Adds complexity across the stack for marginal benefit | Multiple choice only for v1; multiple choice is the highest-signal format for AI-generated questions |
| Real-time collaborative sessions | Study together live | WebSockets, presence, conflict resolution, session sync — entirely different product surface. Massive scope | Out of scope; focus on solo learning excellence |
| AI-graded short answer / essay | "More interactive" learning | Open-ended grading is a notoriously hard AI problem (hallucination, rubric consistency). High risk of user-visible AI errors | Multiple choice sidesteps grading entirely; defer until grading quality can be validated |

---

## Feature Dependencies

```
[URL Input Path]
    └──requires──> [Web Scraping / Content Extraction]
                       └──requires──> [Text Cleaning / Chunking]
                                          └──feeds──> [AI Generation Pipeline]

[Topic Description Input Path]
    └──requires──> [Deep Research Agent (AI web search / synthesis)]
                       └──requires──> [Hallucination guardrails]
                       └──feeds──> [AI Generation Pipeline]

[AI Generation Pipeline]
    └──produces──> [Structured Notes]
    └──produces──> [Flashcards]
    └──produces──> [Multiple Choice Quiz + Explanations]
    └──provides context for──> [In-Session AI Chat]

[Tutoring Type Selection]
    └──modifies──> [AI Generation Pipeline] (prompt shaping)
    └──modifies──> [In-Session AI Chat] (response register)

[In-Session AI Chat]
    └──requires──> [Session Content Context] (notes/flashcards/quiz available)
    └──requires──> [Streaming response support] (UX requirement)

[Session Shareable Link] (v1.x differentiator)
    └──requires──> [Ephemeral Server-Side Storage] (Redis/TTL)
    └──conflicts──> [Pure browser-ephemeral model]

[Spaced Repetition Scheduling] (deferred)
    └──requires──> [User Accounts]
    └──requires──> [Cross-session persistence]

[User Accounts] (deferred)
    └──enables──> [Cross-session progress tracking]
    └──enables──> [Spaced repetition scheduling]
    └──enables──> [Gamification]
```

### Dependency Notes

- **AI Generation Pipeline requires Content Extraction to complete first:** The generation step cannot begin until source text is extracted, cleaned, and scoped by the focus prompt. This is a serial dependency with meaningful latency implications — progress feedback is critical.
- **In-Session AI Chat requires generation to complete first:** The chat must be grounded in the session content; it cannot be useful before notes/flashcards/quiz exist. The chat context window must include the generated materials.
- **Tutoring Type modifies all generation outputs:** This is a cross-cutting concern applied via prompt shaping. The tutoring type selection must be captured before the generation pipeline runs — it cannot be changed mid-session without regenerating.
- **Topic Description path (deep research) requires its own pipeline branch:** This path is significantly more complex than the URL path. It involves AI-driven web research (Perplexity-style), synthesis, and higher hallucination risk. It should be treated as a separate pipeline segment with its own validation logic.
- **Shareable session links conflict with pure browser-ephemeral model:** Browser sessionStorage/localStorage cannot be shared across devices. A shareable link requires server-side ephemeral storage (e.g., Redis with a TTL like 24-48 hours). This is a deliberate architectural decision point.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [x] **URL input + focus prompt** — Core input path; most users have an article or doc they want to study
- [x] **Topic description input** — Expands use cases; enables "I want to learn X" without a source
- [x] **Tutoring type selection (Micro / Kid / Advanced)** — Key differentiator; defined upfront; low implementation cost vs. high perceived value
- [x] **Structured notes generation** — Primary output; sets quality bar for the product
- [x] **Flashcard generation** — Expected by any study tool user; pairs with notes
- [x] **Multiple-choice quiz generation** — Completes the active recall loop; multiple choice is reliable to generate and grade
- [x] **Tabbed single-page session view (Notes / Flashcards / Quiz)** — Reduces context switching; all content in one place
- [x] **In-session AI chat** — Post-ChatGPT expectation; grounded in session content
- [x] **In-session completion state tracking (flashcards, quiz)** — Lightweight; browser state only; gives users sense of progress
- [x] **Progress/streaming feedback during generation** — Not a feature but a launch requirement; silent waits kill first impressions
- [x] **Ephemeral sessions (no auth)** — Eliminates the biggest drop-off point for new users

### Add After Validation (v1.x)

Features to add once core loop is working and users return.

- [ ] **Quiz answer explanations** — High value, medium cost; show why the correct answer is right. Add when quiz quality is validated.
- [ ] **Shareable session link (ephemeral, TTL-based)** — Addresses "save my session" and sharing use cases without full accounts. Add when users start asking "how do I come back to this?"
- [ ] **Copy to clipboard for flashcards/notes** — Low cost, practical; add when export requests surface consistently.
- [ ] **Keyboard navigation for flashcards and quiz** — Accessibility and power-user quality-of-life; add when polish phase begins.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] **User accounts and authentication** — Unlocks persistence, SRS, personalization. Defer until there's validated demand for returning users.
- [ ] **Cross-session progress tracking** — Requires accounts; defer.
- [ ] **Spaced repetition scheduling** — Requires accounts + scheduling logic; defer.
- [ ] **Video / YouTube URL support** — Separate pipeline; high complexity; defer until URL/topic paths are mature.
- [ ] **Export to PDF / Anki / Notion** — Power-user feature; low frequency; defer.
- [ ] **Gamification (streaks, XP)** — Requires accounts; defer.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| URL input + focus prompt | HIGH | MEDIUM | P1 |
| Topic description input (deep research) | HIGH | HIGH | P1 |
| Tutoring type selection | HIGH | LOW | P1 |
| Structured notes generation | HIGH | MEDIUM | P1 |
| Flashcard generation | HIGH | LOW-MEDIUM | P1 |
| Multiple-choice quiz generation | HIGH | MEDIUM | P1 |
| Tabbed single-page session view | HIGH | LOW | P1 |
| In-session AI chat | HIGH | MEDIUM | P1 |
| Generation progress / streaming feedback | HIGH | LOW | P1 |
| In-session completion tracking | MEDIUM | LOW | P1 |
| Quiz answer explanations | HIGH | MEDIUM | P2 |
| Shareable session link (ephemeral) | MEDIUM | MEDIUM | P2 |
| Copy to clipboard | MEDIUM | LOW | P2 |
| Keyboard navigation | MEDIUM | LOW | P2 |
| User accounts / auth | HIGH | HIGH | P3 |
| Spaced repetition scheduling | HIGH | HIGH | P3 |
| Video / YouTube ingestion | MEDIUM | HIGH | P3 |
| Export (PDF / Anki / Notion) | MEDIUM | MEDIUM | P3 |
| Gamification | MEDIUM | HIGH | P3 |

---

## Competitor Feature Analysis

Key competitors analyzed (from training data, mid-2025): Khanmigo (Khan Academy AI), Quizlet Q-Chat, StudyFetch, Socratic by Google, Photomath, Perplexity (used as study tool), ChatGPT Edu, Notion AI.

| Feature | Khanmigo | Quizlet Q-Chat | StudyFetch | Super Tutor Approach |
|---------|----------|----------------|------------|----------------------|
| Content ingestion (URL) | No — curriculum-locked | No — user uploads flashcards | Yes — URL and PDF | Yes — URL + focus prompt |
| Structured notes | Partial (Socratic Q&A) | No | Yes | Yes — primary output |
| Flashcards | No (Quizlet does) | Yes | Yes — AI-generated | Yes |
| Quiz / assessment | Yes | Yes | Yes | Yes — multiple choice |
| Tone adaptation | Limited | No | No | Yes — 3 tutoring types (differentiator) |
| In-session AI chat | Yes — core feature | Yes — Q-Chat | Yes | Yes |
| No account required | No — Khan account required | No — account required | Partial | Yes — v1 fully ephemeral |
| Deep topic research | No | No | Partial | Yes — AI-researched topic path |
| Focus prompt for URL | No | No | No | Yes (differentiator) |
| Single-page session | No | No | No | Yes (differentiator) |

**Key competitive observation:** Most competitors are either account-gated from the start (Khanmigo, Quizlet), curriculum-locked (Khanmigo), or require users to upload their own content (Quizlet). Super Tutor's combination of URL + focus prompt + tone adaptation + zero friction is genuinely differentiated — no major competitor has all three simultaneously as of mid-2025.

---

## Sources

- Training data knowledge: Khanmigo (khanacademy.org/khan-labs), Quizlet Q-Chat, StudyFetch, Socratic by Google, Photomath, Perplexity, ChatGPT Edu — all observed through mid-2025. Confidence: MEDIUM (training data, not live verification).
- Product patterns: Active recall, spaced repetition, and Bloom's taxonomy are established educational science; feature implications are HIGH confidence.
- Project context: /Users/mohammedhafiz/Desktop/Personal/super_tutor/.planning/PROJECT.md — already-decided features treated as constraints, not open questions.
- Note: WebSearch and WebFetch were unavailable during this research session. Findings reflect training data synthesis. Competitor-specific feature claims should be spot-checked before roadmap finalization if live verification becomes available.

---
*Feature research for: AI Tutoring / Ed-Tech Web App (Super Tutor)*
*Researched: 2026-02-18*
