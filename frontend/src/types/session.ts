export type TutoringType = "micro_learning" | "teaching_a_kid" | "advanced";

export type SessionType = "url" | "topic" | "paste";

export interface SessionRequest {
  url?: string;
  paste_text?: string;
  topic_description?: string;
  tutoring_type: TutoringType;
  focus_prompt?: string;
  generate_flashcards?: boolean;
  generate_quiz?: boolean;
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface QuizQuestion {
  question: string;
  options: string[]; // exactly 4
  answer_index: number; // 0-3
}

export interface SessionResult {
  session_id: string;
  source_title: string;
  tutoring_type: TutoringType;
  session_type: SessionType;
  sources?: string[];
  notes: string; // markdown
  flashcards: Flashcard[];
  quiz: QuizQuestion[];
  chat_intro: string; // persona-adapted greeting shown as first chat bubble
  errors?: Record<string, string>; // per-section errors e.g. { flashcards: "...", quiz: "..." }
}

// SSE event shapes from the backend stream
export interface ProgressEvent {
  message: string;
}

// CompleteEvent is now the full session payload — the backend sends all data in one shot.
export type CompleteEvent = SessionResult;

export interface ErrorEvent {
  kind: "paywall" | "invalid_url" | "empty" | "unreachable";
}

// Base SSE steps — URL/paste paths
export const SSE_STEPS_BASE = [
  "Reading the article...",
  "Crafting your notes...",
  "Generating title...",
] as const;

// Topic path base steps
export const TOPIC_SSE_STEPS_BASE = [
  "Researching your topic...",
  "Crafting your notes...",
  "Generating title...",
] as const;

// Legacy aliases kept for backward compat with loading page
export const SSE_STEPS = SSE_STEPS_BASE;
export const TOPIC_SSE_STEPS = TOPIC_SSE_STEPS_BASE;

// Optional steps appended when the user opted in
export const FLASHCARD_STEP = "Creating flashcards..." as const;
export const QUIZ_STEP = "Building quiz questions..." as const;

/**
 * Build the ordered list of expected SSE progress messages for the loading page.
 * Mirrors the server-side run_session_workflow progress emission order.
 */
export function buildExpectedSteps(
  inputMode: "url" | "topic" | "paste",
  generateFlashcards: boolean,
  generateQuiz: boolean,
): string[] {
  const base = inputMode === "topic"
    ? [...TOPIC_SSE_STEPS_BASE]
    : [...SSE_STEPS_BASE];

  // Insert optional steps before "Generating title..."
  const titleIndex = base.indexOf("Generating title...");
  const extras: string[] = [];
  if (generateFlashcards) extras.push(FLASHCARD_STEP);
  if (generateQuiz) extras.push(QUIZ_STEP);

  return [
    ...base.slice(0, titleIndex),
    ...extras,
    ...base.slice(titleIndex),
  ];
}

export interface WarningEvent {
  message: string;
}
