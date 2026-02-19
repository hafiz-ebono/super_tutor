"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SSE_STEPS, ProgressEvent, CompleteEvent, ErrorEvent } from "@/types/session";

const PROGRESS_WEIGHTS = [10, 40, 70, 100] as const;

export default function LoadingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const sessionId = searchParams.get("session_id");
  const tutoringType = searchParams.get("tutoring_type") ?? "";
  const focusPrompt = searchParams.get("focus_prompt") ?? "";

  const [currentMessage, setCurrentMessage] = useState<string>(SSE_STEPS[0]);
  const [stepIndex, setStepIndex] = useState(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!sessionId) {
      router.replace("/create");
      return;
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    const es = new EventSource(`${apiUrl}/sessions/${sessionId}/stream`);
    esRef.current = es;

    es.addEventListener("progress", (e: MessageEvent) => {
      const data: ProgressEvent = JSON.parse(e.data);
      setCurrentMessage(data.message);
      setStepIndex((i) => Math.min(i + 1, SSE_STEPS.length - 1));
    });

    es.addEventListener("complete", (e: MessageEvent) => {
      const data: CompleteEvent = JSON.parse(e.data);
      es.close();
      setStepIndex(SSE_STEPS.length - 1);
      setTimeout(() => router.push(`/study/${data.session_id}`), 400);
    });

    es.addEventListener("error", (e: MessageEvent) => {
      es.close();
      try {
        const data: ErrorEvent = JSON.parse(e.data);
        router.push(`/create?error=${data.kind}&tutoring_type=${tutoringType}&focus_prompt=${encodeURIComponent(focusPrompt)}`);
      } catch {
        router.push(`/create?error=empty&tutoring_type=${tutoringType}&focus_prompt=${encodeURIComponent(focusPrompt)}`);
      }
    });

    es.onerror = () => {
      es.close();
      router.push(`/create?error=unreachable&tutoring_type=${tutoringType}&focus_prompt=${encodeURIComponent(focusPrompt)}`);
    };

    return () => es.close();
  }, [sessionId, router, tutoringType, focusPrompt]);

  const progressPercent = PROGRESS_WEIGHTS[Math.min(stepIndex, PROGRESS_WEIGHTS.length - 1)];

  return (
    <main className="flex flex-col items-center justify-center min-h-[calc(100vh-56px)] p-8">
      {/* Thin progress bar at top of page */}
      <div className="fixed top-14 left-0 right-0 h-0.5 bg-zinc-100">
        <div
          className="h-full bg-blue-600 transition-all duration-500 ease-in-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Status */}
      <div className="flex flex-col items-center text-center gap-4">
        <span className="spinner" />
        <p className="text-base font-medium text-zinc-900">{currentMessage}</p>
        <p className="text-sm text-zinc-400">This usually takes 30–60 seconds</p>
      </div>
    </main>
  );
}
