"use client";
import { Suspense, useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { buildProgressSteps, SessionPollResponse } from "@/types/session";

const POLL_INTERVAL_MS = 3000;   // check backend every 3 seconds
const STEP_ADVANCE_MS = 15000;   // advance fake progress message every 15 seconds
const TIMEOUT_MS = 5 * 60 * 1000; // give up after 5 minutes

const ERROR_LABELS: Record<string, { title: string; body: string }> = {
  paywall: {
    title: "Couldn't read that page",
    body: "This looks like a paywalled article. Try pasting the article text instead.",
  },
  invalid_url: {
    title: "Couldn't read that page",
    body: "The URL doesn't look valid. Check it and try again, or paste the article text.",
  },
  empty: {
    title: "Not enough content",
    body: "The page loaded but didn't have enough readable text.",
  },
  rate_limit: {
    title: "Daily AI token limit reached",
    body: "The free tier token quota has been used up for today. Try creating a new session later.",
  },
  workflow_error: {
    title: "Something went wrong",
    body: "The session couldn't be generated. Please try again.",
  },
  invalid_input: {
    title: "Invalid input",
    body: "Please provide a URL, pasted text, or topic description.",
  },
  timeout: {
    title: "This is taking longer than expected",
    body: "The session may still be processing. Please try again in a moment.",
  },
};

function extractRetryTime(errorMessage: string): string | null {
  // Parses "Please try again in 4h53m41.28s" from provider error messages
  const match = errorMessage.match(/try again in ([0-9hms.]+)/i);
  return match ? match[1] : null;
}

function getErrorLabel(kind: string, errorMessage?: string): { title: string; body: string } {
  const base = ERROR_LABELS[kind] ?? ERROR_LABELS.workflow_error;
  if (kind === "rate_limit" && errorMessage) {
    const retryTime = extractRetryTime(errorMessage);
    return {
      title: base.title,
      body: retryTime
        ? `The daily token limit has been reached. Please try again in ${retryTime}. You can create a new session when the limit resets.`
        : base.body,
    };
  }
  return base;
}

function LoadingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const tutoringType = searchParams.get("tutoring_type") ?? "";
  const focusPrompt = searchParams.get("focus_prompt") ?? "";
  const inputMode = (searchParams.get("input_mode") ?? "url") as "url" | "topic" | "paste" | "upload";
  const generateFlashcards = searchParams.get("generate_flashcards") === "true";
  const generateQuiz = searchParams.get("generate_quiz") === "true";

  const steps = buildProgressSteps(inputMode, generateFlashcards, generateQuiz);

  const [stepIndex, setStepIndex] = useState(0);
  const [error, setError] = useState<{ kind: string; title: string; body: string } | null>(null);

  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startTimeRef = useRef(Date.now());

  useEffect(() => {
    if (!sessionId) {
      router.replace("/create");
      return;
    }

    // Fast path: session already completed in a previous tab/visit
    const cached = localStorage.getItem(`session:${sessionId}`);
    if (cached) {
      router.replace(`/study/${sessionId}`);
      return;
    }

    const controller = new AbortController();
    const { signal } = controller;
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    // Cycle through progress steps every STEP_ADVANCE_MS.
    // Stops advancing at the last step so the message stays stable once reached.
    stepTimerRef.current = setInterval(() => {
      setStepIndex((i) => (i + 1 < steps.length ? i + 1 : i));
    }, STEP_ADVANCE_MS);

    async function poll() {
      if (signal.aborted) return;

      if (Date.now() - startTimeRef.current > TIMEOUT_MS) {
        clearInterval(stepTimerRef.current!);
        setError({ kind: "timeout", ...getErrorLabel("timeout") });
        return;
      }

      try {
        const res = await fetch(`${apiUrl}/sessions/${sessionId}`, { signal });

        if (!res.ok) {
          // 404 — session not found (invalid session_id or expired)
          clearInterval(stepTimerRef.current!);
          setError({ kind: "empty", ...getErrorLabel("empty") });
          return;
        }

        const data: SessionPollResponse = await res.json();

        if (data.status === "complete") {
          clearInterval(stepTimerRef.current!);
          // Strip the lifecycle `status` field before caching as SessionResult
          const { status: _s, ...sessionData } = data;
          localStorage.setItem(`session:${sessionId}`, JSON.stringify(sessionData));
          setStepIndex(steps.length - 1);
          setTimeout(() => router.push(`/study/${sessionId}`), 400);
          return;
        }

        if (data.status === "failed") {
          clearInterval(stepTimerRef.current!);
          const label = getErrorLabel(data.error_kind, data.error_message);
          setError({ kind: data.error_kind, ...label });
          return;
        }

        // status === "pending" — schedule next poll
        if (!signal.aborted) setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        // AbortError means the effect cleaned up (unmount/StrictMode) — stop silently
        if ((err as Error).name === "AbortError") return;
        // Network error — keep retrying; the backend may be briefly unavailable
        if (!signal.aborted) setTimeout(poll, POLL_INTERVAL_MS);
      }
    }

    poll();

    return () => {
      controller.abort();
      clearInterval(stepTimerRef.current!);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const progressPercent =
    steps.length > 1
      ? Math.round(10 + (stepIndex / (steps.length - 1)) * 85)
      : 50;

  // Error state — inline, with retry options
  if (error) {
    return (
      <main className="flex flex-col items-center justify-center min-h-[calc(100vh-56px)] p-8">
        <div className="flex flex-col items-center text-center gap-5 max-w-sm">
          <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center shrink-0">
            <svg
              className="w-6 h-6 text-red-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
            >
              <circle cx="12" cy="12" r="10" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01" />
            </svg>
          </div>

          <div>
            <p className="font-semibold text-zinc-900 text-base">{error.title}</p>
            <p className="text-sm text-zinc-500 mt-1.5">{error.body}</p>
          </div>

          <div className="flex gap-3 flex-wrap justify-center">
            <button
              onClick={() =>
                router.push(
                  `/create?error=${error.kind}&tutoring_type=${tutoringType}&focus_prompt=${encodeURIComponent(focusPrompt)}&input_mode=${inputMode}`
                )
              }
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
            >
              Try again
            </button>
            <button
              onClick={() => router.push("/create")}
              className="px-4 py-2 text-sm font-medium text-zinc-600 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors"
            >
              Start over
            </button>
          </div>
        </div>
      </main>
    );
  }

  // Progress state
  return (
    <main className="flex flex-col items-center justify-center min-h-[calc(100vh-56px)] p-8">
      {/* Thin progress bar at top */}
      <div className="fixed top-14 left-0 right-0 h-0.5 bg-zinc-100">
        <div
          className="h-full bg-blue-600 transition-all duration-1000 ease-in-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="flex flex-col items-center text-center gap-4">
        <span className="spinner" />
        <p className="text-base font-medium text-zinc-900">{steps[stepIndex]}</p>
        <p className="text-sm text-zinc-400">This usually takes 30–60 seconds</p>
      </div>
    </main>
  );
}

export default function LoadingPage() {
  return (
    <Suspense>
      <LoadingContent />
    </Suspense>
  );
}
