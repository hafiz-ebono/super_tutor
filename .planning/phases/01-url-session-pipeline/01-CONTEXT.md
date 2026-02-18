# Phase 1: URL Session Pipeline - Context

**Gathered:** 2026-02-18
**Status:** Ready for planning

<domain>
## Phase Boundary

End-to-end session creation from URL to study page. User submits a URL, a focus prompt, and a tutoring type — Agno agents extract the content and generate notes, flashcards, and a quiz. User sees real-time progress during generation and lands on a tabbed study page. URL extraction failures surface inline with a text-paste fallback. Configurable AI provider/model via environment. Session history, multiple sessions, and flashcard flip interaction are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Session creation form
- Landing page is a marketing/intro page with a CTA that leads to a dedicated create page (e.g., /create)
- Create page has all three fields on one screen: URL input, tutoring mode picker, and optional focus prompt — submitted together
- Tutoring mode presented as three selectable cards with brief descriptions (Micro Learning, Teaching a Kid, Advanced)
- Focus prompt field labeled "What do you want to focus on?" — clearly optional, free-text hint to guide the AI's emphasis

### Progress experience
- On submit, the create page transitions to a full-screen loading state (not an overlay)
- Step messages use a friendly, slightly playful tone: "Reading the article...", "Crafting your notes...", "Making your flashcards...", "Building your quiz..."
- A simple progress bar at the top of the loading screen advances as each step completes
- On generation complete, user is automatically redirected to the study page — no button required

### Study page layout
- Left sidebar navigation — user clicks Notes, Flashcards, or Quiz in the sidebar to switch content areas
- Sidebar shows: source title and tutoring mode label only (no URL, no timestamp)
- Sidebar includes a "New session" link so the user can easily start over
- Notes section: structured markdown — headings, bullet points, bold key terms — reads like a formatted study guide
- Flashcards section: grid layout showing all cards with the question side visible (flip interaction is Phase 3)
- Quiz section: multiple choice, one question at a time — user answers, sees instant feedback (correct/wrong), moves to next
- After quiz completion: score summary (X/Y correct) followed by review of each question showing the correct answer

### URL failure & fallback
- When URL extraction fails, user is returned to the create form with an inline error below the URL field
- Error messaging: friendly top-level message ("We couldn't read that page") with a specific pointer beneath it indicating the likely cause (paywall, invalid URL, empty/unreadable page)
- A textarea appears inline below the error message: "Paste the article text instead" — user can paste content and resubmit
- When fallback textarea appears, mode selection and focus prompt remain filled in — only the URL field is cleared
- After paste submission, user goes through the same full-screen progress screen as the URL path — consistent experience

### Claude's Discretion
- Textarea character limit and input guidance (minimum length, max length hints)
- Handling of bad/garbled pasted text (client-side validation threshold or pass-through to agents)
- Exact progress bar segment widths and animation style
- Copy for the landing page CTA and create page headings
- Error pointer message wording for each failure type

</decisions>

<specifics>
## Specific Ideas

- Progress step messages should feel like a tutor actively working: "Reading the article...", "Crafting your notes...", "Making your flashcards...", "Building your quiz..."
- Quiz is question-by-question with instant per-answer feedback, not submit-all-at-end
- Quiz results show both the score AND a full review — user can learn from mistakes without re-taking

</specifics>

<deferred>
## Deferred Ideas

- Session history and multi-session support — user requested the ability to store generated sessions and navigate between them from a home/dashboard view. This is a meaningful capability on its own and belongs in a future phase.

</deferred>

---

*Phase: 01-url-session-pipeline*
*Context gathered: 2026-02-18*
