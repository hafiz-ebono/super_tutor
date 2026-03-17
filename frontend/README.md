# Super Tutor — Frontend

Next.js 14 (App Router) frontend for Super Tutor. Provides the session creation form (URL, topic, paste, or file upload), a real-time SSE progress screen, and an interactive study view with notes, flashcards, quiz, a grounded chat panel, and a Personal Tutor tab backed by a 5-specialist Agno Team.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14 (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Markdown rendering | react-markdown + remark-gfm |
| Session persistence | `localStorage` (client-side only) |
| Backend communication | `fetch` + native `EventSource` (SSE) |

---

## Directory Layout

```
frontend/src/
├── app/
│   ├── layout.tsx                    # Root layout (nav, global styles)
│   ├── page.tsx                      # Landing page — hero + feature cards + recent sessions
│   ├── create/
│   │   └── page.tsx                  # Session creation form (URL / topic / paste / upload tabs)
│   ├── loading/
│   │   └── page.tsx                  # SSE progress screen (EventSource consumer)
│   └── study/
│       └── [sessionId]/
│           └── page.tsx              # Study session view (notes / flashcards / quiz / chat)
├── hooks/
│   └── useRecentSessions.ts          # Recent sessions hook (localStorage-backed)
└── types/
    └── session.ts                    # Shared TypeScript types for all session data
```

---

## Pages

### Landing Page — `/`

**File:** `src/app/page.tsx`

- Displays a hero section with a CTA to `/create`
- Shows three tutoring mode feature cards
- Lists up to 5 recent sessions from `localStorage` (via `useRecentSessions`)

---

### Create Page — `/create`

**File:** `src/app/create/page.tsx`

The session creation form. Handles four input modes:

```mermaid
flowchart TD
    A[Select tutoring mode\nmicro_learning / teaching_a_kid / advanced] --> B{Input mode tab}
    B -- Article URL --> C[URL input field]
    B -- Topic description --> D[Topic textarea]
    B -- Paste text --> E[Paste textarea]
    B -- Upload file --> F[PDF or DOCX file picker\nmax 20 MB]
    C -- URL extraction fails --> G[Inline error + paste fallback textarea]
    D --> H[Focus prompt\noptional]
    E --> H
    G --> H
    F --> I[handleUploadSubmit\nPOST /sessions/upload multipart/form-data\ninline SSE consumer]
    H --> J[Submit: POST /sessions]
    J --> K[navigate /loading?session_id=...]
    I -- progress/complete events --> L[navigate /loading?session_id=...\nor show error inline]
```

**Error recovery:** If a URL session fails (paywall, invalid URL, empty content), the user is redirected back to `/create` with `?error=<kind>` query params. The form restores their tutoring mode and focus prompt, and reveals a paste-text fallback input.

**Upload flow:** The upload tab POSTs directly to `POST /sessions/upload` as `multipart/form-data` and consumes the SSE stream inline (no redirect to `/loading` until the `complete` event arrives). Pre-stream validation errors from the server (400/413/422) are displayed inline in the upload tab.

---

### Loading Page — `/loading`

**File:** `src/app/loading/page.tsx`

Connects to the backend SSE stream and shows real-time progress.

```mermaid
sequenceDiagram
    participant Page as LoadingPage
    participant ES as EventSource
    participant API as Backend SSE

    Page->>ES: new EventSource(/sessions/{id}/stream)
    API-->>ES: event: progress {message}
    ES-->>Page: update status message + progress bar
    API-->>ES: event: warning {message}
    ES-->>Page: show amber warning banner
    API-->>ES: event: complete {SessionResult}
    ES-->>Page: localStorage.setItem(session)\nnavigate /study/{id}
    API-->>ES: event: error {kind}
    ES-->>Page: navigate /create?error=...
```

**Progress bar:** Advances through weighted steps derived from `buildProgressSteps()` as SSE `progress` events arrive, giving visual feedback even before the final `complete` event. Steps are calculated from `inputMode`, `generateFlashcards`, and `generateQuiz` flags stored in `localStorage` before navigation.

---

### Study Page — `/study/[sessionId]`

**File:** `src/app/study/[sessionId]/page.tsx`

The main study view, loaded entirely from `localStorage`. Three tabs + an optional chat panel.

```mermaid
flowchart TD
    A[Load session from localStorage] --> B{session found?}
    B -- No --> C[Show error + link to /create]
    B -- Yes --> D[Render study view]
    D --> E{Active tab}
    E -- Notes --> F[ReactMarkdown prose view]
    E -- Flashcards --> G{flashcards exist?}
    E -- Quiz --> H{quiz exists?}
    G -- Yes --> I[Flip-card grid]
    G -- No --> J[Generate Flashcards button\nPOST /sessions/id/regenerate/flashcards]
    H -- Yes --> K[Interactive quiz\nanswering → reviewing phases]
    H -- No --> L[Generate Quiz button\nPOST /sessions/id/regenerate/quiz]
    D --> M[Floating chat bubble]
    M --> N[Sliding chat panel\nPOST /chat/stream SSE]
```

#### Tabs

| Tab | Content | Generation |
|-----|---------|-----------|
| **Notes** | Markdown rendered with `react-markdown` | Generated during session creation |
| **Flashcards** | Flip-card grid (8–12 cards) | On-demand via `POST /sessions/{id}/regenerate/flashcards` |
| **Quiz** | Multiple-choice, question-by-question, then review | On-demand via `POST /sessions/{id}/regenerate/quiz` |
| **Tutor** | Persistent multi-turn chat with a 5-specialist Agno Team | Live via `POST /tutor/{id}/stream` |

#### Chat Panel (floating)

- Floating button (bottom-right) toggles a slide-in panel
- Opens with a persona-adapted greeting (`chat_intro` from `SessionResult`)
- Streams tokens from `POST /chat/stream` using `ReadableStream` + `TextDecoder`
- Sends only `{message, tutoring_type, session_id, chat_reset_id?}` — notes are loaded server-side from SQLite, not sent by the client
- "Reset chat" button generates a new `chat_reset_id` (UUID) so the backend starts a fresh conversation history
- Chat history is persisted to `localStorage` as `chat:{sessionId}` and displayed client-side

#### Tutor Tab

- Dedicated full-panel chat interface (not the floating bubble)
- Streams tokens from `POST /tutor/{session_id}/stream` using `ReadableStream` + `TextDecoder`
- Sends only `{message, tutoring_type, session_id, tutor_reset_id}` — source content and notes are loaded server-side
- Auto-triggers an introduction message on first open (fires once per session, tracked via `tutor_intro_seen:{sessionId}` in `localStorage`)
- `tutor_reset_id` is persisted in `localStorage` (`tutor_reset_id:{sessionId}`); changing it starts a fresh conversation in SQLite without losing old history rows
- Tutor history is persisted to `localStorage` as `tutor_history:{sessionId}`
- Handles SSE events: `stream_start`, `token`, `done`, `rejected` (off-topic guardrail), `error`

---

## Data Flow

```mermaid
flowchart LR
    Create["Create Page\n/create"] -- POST /sessions\nor POST /sessions/upload --> API
    API -- session_id --> Loading["Loading Page\n/loading"]
    Loading -- EventSource SSE --> API
    API -- complete event\nSessionResult --> Loading
    Loading -- localStorage.setItem --> LS[(localStorage)]
    Loading -- navigate --> Study["Study Page\n/study/id"]
    Study -- localStorage.getItem --> LS
    Study -- POST regenerate --> API
    Study -- POST chat/stream --> API
```

**Why `localStorage`?**
Session data is stored client-side so the study page loads instantly without a round-trip. The backend only stores workflow session state and agent traces for observability — it does not serve session data back to the frontend.

---

## State Management

There is no global state library. State lives in:

| Store | Contents | TTL |
|-------|----------|-----|
| `localStorage: session:{id}` | Full `SessionResult` | Until cleared by browser / user |
| `localStorage: chat:{id}` | Floating chat history array (display only) | Until cleared by browser / user |
| `localStorage: tutor_history:{id}` | Tutor tab conversation history | Until cleared by browser / user |
| `localStorage: tutor_reset_id:{id}` | Active `tutor_reset_id` for conversation namespacing | Until cleared by browser / user |
| `localStorage: tutor_intro_seen:{id}` | Whether the auto-intro has fired for this session | Until cleared by browser / user |
| `localStorage: super_tutor_recent_sessions` | Last 5 session stubs | Managed by `useRecentSessions` hook |
| React `useState` | UI-only state (active tab, quiz phase, chat open, tutor streaming) | Page lifetime |

### useRecentSessions Hook

**File:** `src/hooks/useRecentSessions.ts`

Maintains a list of up to 5 recent session stubs. On each `saveSession()` call:
1. Deduplicates by `session_id`
2. Prepends the new entry
3. Evicts the oldest if `> 5` entries
4. Shows a toast notification when eviction occurs
5. Validates that the full session data still exists in `localStorage` before returning

---

## TypeScript Types

**File:** `src/types/session.ts`

Key types shared across all pages:

```typescript
type TutoringType = "micro_learning" | "teaching_a_kid" | "advanced";
type SessionType = "url" | "topic" | "paste" | "upload";

interface SessionResult {
  session_id: string;
  source_title: string;
  tutoring_type: TutoringType;
  session_type: SessionType;
  sources?: string[];        // Research sources for topic sessions
  notes: string;             // Markdown
  flashcards: Flashcard[];
  quiz: QuizQuestion[];
  chat_intro: string;        // Persona-adapted greeting shown as first chat bubble
  errors?: Record<string, string>; // Per-section errors e.g. { flashcards: "..." }
}

interface Flashcard { front: string; back: string; }
interface QuizQuestion { question: string; options: string[]; answer_index: number; }
```

SSE event types mirror the backend stream events: `ProgressEvent`, `CompleteEvent`, `ErrorEvent`, `WarningEvent`.

#### buildProgressSteps

```typescript
function buildProgressSteps(
  inputMode: "url" | "topic" | "paste" | "upload",
  generateFlashcards: boolean,
  generateQuiz: boolean,
): string[]
```

Returns an ordered list of progress messages for the loading page, matching the server-side workflow step order. `buildExpectedSteps` is kept as a legacy alias.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Base URL of the backend API, e.g. `http://localhost:8000` |

---

## Running Locally

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

Open `http://localhost:3000`.

---

## Building for Production

```bash
npm run build
npm start
```
