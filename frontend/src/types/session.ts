export type TutoringType = "micro_learning" | "teaching_a_kid" | "advanced";

export type SessionType = "url" | "topic" | "paste" | "upload";

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
  was_truncated: boolean; // true when the source document exceeded the char limit and was cut
  errors?: Record<string, string>; // per-section errors e.g. { flashcards: "...", quiz: "..." }
}

// ---------------------------------------------------------------------------
// Poll response shapes from GET /sessions/{id}
// ---------------------------------------------------------------------------

export type SessionPollResponse =
  | { status: "pending" }
  | { status: "failed"; error_kind: string; error_message: string }
  | ({ status: "complete" } & SessionResult);

// ---------------------------------------------------------------------------
// Progress step messages shown while polling (same order as workflow steps)
// ---------------------------------------------------------------------------

const BASE_STEPS_URL = [
  "Reading the article...",
  "Crafting your notes...",
  "Generating title...",
] as const;

const BASE_STEPS_TOPIC = [
  "Researching your topic...",
  "Crafting your notes...",
  "Generating title...",
] as const;

const BASE_STEPS_UPLOAD = [
  "Extracting document...",
  "Crafting your notes...",
  "Generating title...",
] as const;

export const FLASHCARD_STEP = "Creating flashcards..." as const;
export const QUIZ_STEP = "Building quiz questions..." as const;

/**
 * Build the ordered list of progress messages for the loading page.
 * Mirrors the server-side workflow step order.
 */
export function buildProgressSteps(
  inputMode: "url" | "topic" | "paste" | "upload",
  generateFlashcards: boolean,
  generateQuiz: boolean,
): string[] {
  const base = inputMode === "topic"
    ? [...BASE_STEPS_TOPIC]
    : inputMode === "upload"
    ? [...BASE_STEPS_UPLOAD]
    : [...BASE_STEPS_URL];

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

// Legacy alias — keeps any existing imports working
export const buildExpectedSteps = buildProgressSteps;
