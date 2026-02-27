export type TutoringType = "micro_learning" | "teaching_a_kid" | "advanced";

export type SessionType = "url" | "topic";

export interface SessionRequest {
  url?: string;
  paste_text?: string;
  topic_description?: string;
  tutoring_type: TutoringType;
  focus_prompt?: string;
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
}

// SSE event shapes from the backend stream
export interface ProgressEvent {
  message: string;
}

export interface CompleteEvent {
  session_id: string;
}

export interface ErrorEvent {
  kind: "paywall" | "invalid_url" | "empty" | "unreachable";
}

export const SSE_STEPS = [
  "Reading the article...",
  "Crafting your notes...",
  "Making your flashcards...",
  "Building your quiz...",
] as const;

export const TOPIC_SSE_STEPS = [
  "Researching your topic...",
  "Crafting your notes...",
  "Making your flashcards...",
  "Building your quiz...",
] as const;

export interface WarningEvent {
  message: string;
}
