"use client";
import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SessionResult, TutoringType } from "@/types/session";
import { useRecentSessions } from "@/app/hooks/useRecentSessions";

const MODE_LABELS: Record<TutoringType, string> = {
  micro_learning: "Micro Learning",
  teaching_a_kid: "Teaching a Kid",
  advanced: "Advanced",
};

type Tab = "notes" | "flashcards" | "quiz" | "tutor";

const TAB_ICONS: Record<Tab, React.ReactNode> = {
  notes: (
    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z" />
    </svg>
  ),
  flashcards: (
    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <rect x="2" y="7" width="20" height="14" rx="2" strokeLinecap="round" strokeLinejoin="round" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z" />
    </svg>
  ),
  quiz: (
    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8}>
      <circle cx="12" cy="12" r="10" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 17h.01" />
    </svg>
  ),
  tutor: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} className="w-5 h-5 shrink-0">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l9-5-9-5-9 5 9 5z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z" />
    </svg>
  ),
};

const TAB_LABELS: Record<Tab, string> = {
  notes: "Notes",
  flashcards: "Flashcards",
  quiz: "Quiz",
  tutor: "Tutor",
};

export default function StudyPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();

  const [session, setSession] = useState<SessionResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("notes");

  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState<(number | null)[]>([]);
  const [quizPhase, setQuizPhase] = useState<"answering" | "reviewing">("answering");
  const [flippedCards, setFlippedCards] = useState<Set<number>>(new Set());

  const [generatingFlashcards, setGeneratingFlashcards] = useState(false);
  const [generatingQuiz, setGeneratingQuiz] = useState(false);
  const [flashcardError, setFlashcardError] = useState<string | null>(null);
  const [quizError, setQuizError] = useState<string | null>(null);

  const { saveSession, evictionToast } = useRecentSessions();

  const MAX_MESSAGES = 20; // 10 user + 10 assistant exchanges
  const TUTOR_MAX_MESSAGES = 50; // 25 user + 25 assistant exchanges

  const [chatOpen, setChatOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState<{ role: "user" | "assistant"; content: string }[]>(() => {
    try {
      const stored = localStorage.getItem(`chat:${sessionId}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [chatResetId, setChatResetId] = useState<string>(() => {
    try {
      return localStorage.getItem(`chat_reset_id:${sessionId}`) ?? "v0";
    } catch {
      return "v0";
    }
  });
  const [chatInput, setChatInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const readerRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);

  // Tutor tab state — independent of existing floating chat panel
  const [tutorHistory, setTutorHistory] = useState<{ role: "user" | "assistant"; content: string }[]>(() => {
    try {
      const stored = localStorage.getItem(`tutor_history:${sessionId}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const [tutorIntroSeen, setTutorIntroSeen] = useState<boolean>(() => {
    try {
      return localStorage.getItem(`tutor_intro_seen:${sessionId}`) === "true";
    } catch {
      return false;
    }
  });

  const [isTutorStreaming, setIsTutorStreaming] = useState(false);
  const [tutorInput, setTutorInput] = useState("");
  const [tutorResetId, setTutorResetId] = useState<string>(() => {
    try { return localStorage.getItem(`tutor_reset_id:${sessionId}`) ?? "v0"; } catch { return "v0"; }
  });
  const tutorReaderRef = useRef<ReadableStreamDefaultReader<Uint8Array> | null>(null);
  const tutorIntroTriggeredRef = useRef(false);
  const tutorMessagesEndRef = useRef<HTMLDivElement | null>(null);
  const tutorTextareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Cancel any in-flight streams on unmount to release network connections.
  useEffect(() => {
    return () => {
      readerRef.current?.cancel();
      tutorReaderRef.current?.cancel();
    };
  }, []);

  function toggleFlip(index: number) {
    setFlippedCards((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  // Persist chat history and reset ID to localStorage whenever they change
  useEffect(() => {
    if (chatHistory.length > 0) {
      localStorage.setItem(`chat:${sessionId}`, JSON.stringify(chatHistory));
    }
  }, [chatHistory, sessionId]);

  // Persist tutor history to localStorage whenever it changes (skip during streaming)
  useEffect(() => {
    if (isTutorStreaming) return; // wait until turn is complete
    if (tutorHistory.length > 0) {
      try {
        localStorage.setItem(`tutor_history:${sessionId}`, JSON.stringify(tutorHistory));
      } catch { /* ignore quota errors */ }
    }
  }, [tutorHistory, sessionId, isTutorStreaming]);

  useEffect(() => {
    try {
      localStorage.setItem(`chat_reset_id:${sessionId}`, chatResetId);
    } catch {
      // ignore
    }
  }, [chatResetId, sessionId]);

  // Auto-scroll chat to bottom when chatHistory changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Auto-scroll tutor chat to bottom when tutorHistory changes
  useEffect(() => {
    tutorMessagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tutorHistory]);

  // Intro auto-trigger — fires once when Tutor tab is first opened with no history
  useEffect(() => {
    if (activeTab !== "tutor") return;
    if (tutorIntroSeen || tutorHistory.length > 0) return;
    if (!session || isTutorStreaming) return;
    if (tutorIntroTriggeredRef.current) return; // sync guard against double-trigger on re-render
    tutorIntroTriggeredRef.current = true;
    setTutorIntroSeen(true);
    try {
      localStorage.setItem(`tutor_intro_seen:${sessionId}`, "true");
    } catch { /* ignore */ }
    sendTutorMessage(""); // sendTutorMessage sends sentinel string when empty — see Plan 01
  }, [activeTab, session, sessionId]); // minimal deps — ref+state guards handle the rest

  // Auto-focus textarea when chat panel opens
  useEffect(() => {
    if (chatOpen) {
      // Small timeout to allow panel transition to start before focusing
      const t = setTimeout(() => textareaRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [chatOpen]);

  // Load session from localStorage, falling back to the backend when not cached.
  useEffect(() => {
    async function loadSession() {
      const stored = localStorage.getItem(`session:${sessionId}`);
      if (stored) {
        const data: SessionResult = JSON.parse(stored);
        setSession(data);
        setAnswers(new Array(data.quiz.length).fill(null));
        saveSession({
          session_id: data.session_id,
          source_title: data.source_title,
          tutoring_type: data.tutoring_type,
          session_type: data.session_type ?? "url",
        });
        setLoading(false);
        return;
      }
      // Not in localStorage — check the backend poll endpoint.
      // { status: "pending" }  → redirect to loading page
      // { status: "complete" } → use data directly
      // { status: "failed" }   → show error
      // 404                    → session not found
      try {
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/sessions/${sessionId}`);
        if (!res.ok) {
          setError("Session not found. It may have expired or been created on another device.");
          setLoading(false);
          return;
        }
        const payload = await res.json();
        if (payload.status === "pending") {
          // Workflow still running — redirect to loading page to continue polling
          router.replace(`/loading?session_id=${sessionId}`);
          return;
        }
        if (payload.status === "failed") {
          setError("Session generation failed. Please create a new session.");
          setLoading(false);
          return;
        }
        if (payload.status === "complete") {
          const { status: _s, ...data } = payload as { status: string } & SessionResult;
          localStorage.setItem(`session:${sessionId}`, JSON.stringify(data));
          setSession(data);
          setAnswers(new Array(data.quiz.length).fill(null));
          saveSession({
            session_id: data.session_id,
            source_title: data.source_title,
            tutoring_type: data.tutoring_type,
            session_type: data.session_type ?? "url",
          });
        } else {
          setError("Session not found. It may have expired or been created on another device.");
        }
      } catch {
        setError("Session not found on this device.");
      }
      setLoading(false);
    }
    loadSession();
  }, [sessionId]);

  // CLEAN-02 audit: localStorage session data (session:${sessionId}) retains the `notes` field.
  // This is intentional — notes are rendered client-side in the Notes tab without a backend round-trip.
  // Notes travel backend-to-backend for regenerate/chat (sourced from SQLite); the client keeps its
  // own copy solely for display. No notes field is sent in any API request payload (see API-03).

  // Persist a partial update back to localStorage and state
  function updateSession(patch: Partial<SessionResult>) {
    setSession((prev) => {
      if (!prev) return prev;
      return { ...prev, ...patch };
    });
    // Persist outside state setter — side effects must not live inside React updaters.
    // Use the current persisted value from localStorage to merge, since setSession is async.
    const current = JSON.parse(localStorage.getItem(`session:${sessionId}`) ?? "null");
    if (current) {
      localStorage.setItem(`session:${sessionId}`, JSON.stringify({ ...current, ...patch }));
    }
  }

  async function generateFlashcards() {
    if (!session || generatingFlashcards) return;
    setFlashcardError(null);
    setGeneratingFlashcards(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/sessions/${sessionId}/regenerate/flashcards`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tutoring_type: session.tutoring_type }),
        }
      );
      if (!res.ok) throw new Error("Generation failed");
      const data = await res.json();
      updateSession({ flashcards: data.flashcards });
    } catch {
      setFlashcardError("Failed to generate flashcards. Please try again.");
    } finally {
      setGeneratingFlashcards(false);
    }
  }

  async function generateQuiz() {
    if (!session || generatingQuiz) return;
    setQuizError(null);
    setGeneratingQuiz(true);
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/sessions/${sessionId}/regenerate/quiz`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ tutoring_type: session.tutoring_type }),
        }
      );
      if (!res.ok) throw new Error("Generation failed");
      const data = await res.json();
      updateSession({ quiz: data.quiz });
      setAnswers(new Array(data.quiz.length).fill(null));
      setQuizPhase("answering");
      setCurrentQ(0);
    } catch {
      setQuizError("Failed to generate quiz. Please try again.");
    } finally {
      setGeneratingQuiz(false);
    }
  }

  function selectAnswer(optionIndex: number) {
    if (answers[currentQ] !== null) return;
    const next = [...answers];
    next[currentQ] = optionIndex;
    setAnswers(next);
  }

  function nextQuestion() {
    if (currentQ < session!.quiz.length - 1) {
      setCurrentQ((q) => q + 1);
    } else {
      setQuizPhase("reviewing");
    }
  }

  function resetChat() {
    const newResetId = `v${Date.now()}`;
    setChatResetId(newResetId);
    setChatHistory([]);
    try {
      localStorage.removeItem(`chat:${sessionId}`);
      localStorage.setItem(`chat_reset_id:${sessionId}`, newResetId);
    } catch {
      // ignore
    }
  }

  function resetTutorChat() {
    const newResetId = `v${Date.now()}`;
    setTutorResetId(newResetId);
    setTutorHistory([]);
    setTutorIntroSeen(false);
    tutorIntroTriggeredRef.current = false;
    try {
      localStorage.setItem(`tutor_reset_id:${sessionId}`, newResetId);
      localStorage.removeItem(`tutor_history:${sessionId}`);
      localStorage.removeItem(`tutor_intro_seen:${sessionId}`);
    } catch {
      // ignore
    }
  }

  async function sendMessage() {
    if (!session || !chatInput.trim() || isStreaming) return;
    const userMessage = chatInput.trim();
    setChatInput("");
    
    // If a previous stream left a dangling empty assistant bubble, replace it with an error
    setChatHistory((prev) => {
      const resolved = prev.map((msg) =>
        msg.role === "assistant" && msg.content === ""
          ? { ...msg, content: "Sorry, something went wrong. Please try again." }
          : msg
      );
      return [...resolved, { role: "user" as const, content: userMessage }];
    });
    
    setIsStreaming(true);

    // Add empty assistant placeholder for typing bubble
    setChatHistory((prev) => [...prev, { role: "assistant" as const, content: "" }]);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          tutoring_type: session.tutoring_type,
          chat_reset_id: chatResetId,
        }),
      });

      if (!res.ok || !res.body) throw new Error("Stream request failed");

      const reader = res.body.getReader();
      readerRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // keep incomplete last line in buffer

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const parsed = JSON.parse(raw);
            if (typeof parsed.token === "string") {
              setChatHistory((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last && last.role === "assistant") {
                  next[next.length - 1] = { ...last, content: last.content + parsed.token };
                }
                return next;
              });
            } else if (typeof parsed.error === "string") {
              setChatHistory((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last && last.role === "assistant") {
                  next[next.length - 1] = { ...last, content: parsed.error };
                }
                return next;
              });
              setIsStreaming(false);
              return;
            }
          } catch {
            // Ignore non-JSON data lines (e.g. event: done line)
          }
        }
      }
      
      // Remove empty assistant message if stream completed without content
      setChatHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.role === "assistant" && last.content === "") {
          return prev.slice(0, -1);
        }
        return prev;
      });
    } catch {
      // Replace empty assistant placeholder with error message
      setChatHistory((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === "assistant" && last.content === "") {
          next[next.length - 1] = { ...last, content: "Sorry, something went wrong. Please try again." };
        }
        return next;
      });
    } finally {
      readerRef.current = null;
      setIsStreaming(false);
    }
  }

  async function sendTutorMessage(userMessage: string) {
    if (!session || isTutorStreaming) return;
    setTutorHistory((prev) => {
      const next = userMessage.trim()
        ? [...prev, { role: "user" as const, content: userMessage.trim() }]
        : [...prev];
      return [...next, { role: "assistant" as const, content: "" }];
    });
    setIsTutorStreaming(true);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/tutor/${sessionId}/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage.trim() || "Hello! Please introduce yourself and your capabilities.",
          tutoring_type: session.tutoring_type,
          session_id: sessionId,
          tutor_reset_id: tutorResetId,
        }),
      });

      if (!res.ok || !res.body) throw new Error("Tutor stream failed");

      const reader = res.body.getReader();
      tutorReaderRef.current = reader;
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const parsed = JSON.parse(raw);
            if (typeof parsed.token === "string") {
              setTutorHistory((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant") {
                  next[next.length - 1] = { ...last, content: last.content + parsed.token };
                }
                return next;
              });
            } else if (typeof parsed.error === "string") {
              setTutorHistory((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant") {
                  next[next.length - 1] = { ...last, content: parsed.error };
                }
                return next;
              });
              setIsTutorStreaming(false);
              return;
            } else if (typeof parsed.reason === "string") {
              // GUARD-01 rejection — friendly redirect from TopicRelevanceGuardrail
              setTutorHistory((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                if (last?.role === "assistant") {
                  next[next.length - 1] = { ...last, content: parsed.reason };
                }
                return next;
              });
              setIsTutorStreaming(false);
              return;
            }
          } catch { /* non-JSON line — ignore */ }
        }
      }
      // Remove empty assistant bubble if stream completed without content
      setTutorHistory((prev) => {
        const last = prev[prev.length - 1];
        if (last?.role === "assistant" && last.content.trim() === "") return prev.slice(0, -1);
        return prev;
      });
    } catch (err) {
      console.error("Tutor stream error:", err);
      setTutorHistory((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last?.role === "assistant") {
          if (last.content === "") {
            next[next.length - 1] = { ...last, content: "Sorry, something went wrong. Please try again." };
          } else {
            // Partial content received before cancel/error — mark as truncated
            next[next.length - 1] = { ...last, content: last.content + "\n\n*(Response interrupted)*" };
          }
        }
        return next;
      });
    } finally {
      tutorReaderRef.current = null;
      setIsTutorStreaming(false);
    }
  }

  if (loading) {
    return (
      <main className="flex items-center justify-center min-h-[80vh]">
        <span className="spinner" />
      </main>
    );
  }

  if (error || !session) {
    return (
      <main className="flex items-center justify-center min-h-[80vh]">
        <p className="text-zinc-500 text-sm">
          {error ?? "Session not found."}{" "}
          <Link href="/create" className="text-blue-600 hover:underline">
            Start a new session
          </Link>
        </p>
      </main>
    );
  }

  const correctCount = answers.filter((a, i) => a === session!.quiz[i]?.answer_index).length;

  return (
    <div className="flex" style={{ minHeight: "calc(100vh - 56px)" }}>
      {evictionToast && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-zinc-900 text-white text-xs px-4 py-2.5 rounded-lg shadow-lg toast-slide-up">
          Your oldest session was removed to make space
        </div>
      )}

      {/* Desktop sidebar — hidden on mobile */}
      <aside className="hidden lg:flex w-52 shrink-0 flex-col border-r border-zinc-100 px-3 py-5">
        <div className="mb-5 px-2">
          <p className="font-semibold text-zinc-900 text-sm leading-snug mb-2">
            {session.source_title}
          </p>
          <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-600">
            {MODE_LABELS[session.tutoring_type]}
          </span>
        </div>

        <nav className="flex flex-col gap-0.5">
          {(["notes", "flashcards", "quiz", "tutor"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg text-sm transition-colors ${
                activeTab === tab
                  ? "bg-zinc-100 text-zinc-900 font-medium"
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              {TAB_ICONS[tab]}
              {tab === "tutor" ? "Personal Tutor" : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </nav>

        <div className="mt-auto">
          <Link
            href="/create"
            className="flex items-center gap-2 px-2 py-2 rounded-lg text-xs text-zinc-400 hover:text-zinc-600 hover:bg-zinc-50 transition-colors"
          >
            + New session
          </Link>
        </div>
      </aside>

      {/* Right column */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Mobile meta-header — hidden on desktop */}
        <div className="lg:hidden flex flex-col gap-1.5 px-5 py-3 border-b border-zinc-100">
          <p className="font-semibold text-zinc-900 text-sm leading-snug truncate">
            {session.source_title}
          </p>
          <span className="self-start inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-600">
            {MODE_LABELS[session.tutoring_type]}
          </span>
        </div>

        {/* Main content */}
        <main className={`flex-1 transition-all duration-300 ${activeTab === "tutor" ? "flex flex-col overflow-hidden" : "px-6 py-8 md:pb-8 pb-24"} ${chatOpen ? "lg:mr-[360px]" : ""}`}>

          {/* AI-researched disclaimer — topic sessions only */}
          {session.session_type === "topic" && (
            <div className="mb-6 flex flex-col gap-2 p-4 rounded-xl border border-amber-200 bg-amber-50">
              <p className="text-xs font-medium text-amber-800">
                AI-researched content — verify with primary sources
              </p>
              <p className="text-xs text-amber-700">
                This session was generated from AI web research. The content may contain inaccuracies. Always check primary sources before relying on this material.
              </p>
              {session.sources && session.sources.length > 0 && (
                <div className="flex flex-col gap-1">
                  <p className="text-xs font-medium text-amber-800">Sources used:</p>
                  <ul className="flex flex-col gap-0.5">
                    {session.sources.filter((src) => /^https?:\/\//i.test(src)).map((src, i) => (
                      <li key={i}>
                        <a
                          href={src}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-amber-700 underline hover:text-amber-900 break-all"
                        >
                          {src}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          {/* Notes */}
          {activeTab === "notes" && (
            <article className="prose">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.notes}</ReactMarkdown>
            </article>
          )}

          {/* Flashcards — 4 states: content / generating / error / empty */}
          {activeTab === "flashcards" && (
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 mb-6">Flashcards</h2>

              {session.flashcards.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {session.flashcards.map((card, i) => (
                    <div
                      key={i}
                      className={`flashcard-scene${flippedCards.has(i) ? " is-flipped" : ""}`}
                      style={{ minHeight: "120px", cursor: "pointer" }}
                      onClick={() => toggleFlip(i)}
                      role="button"
                      aria-label={`Flashcard ${i + 1}: ${flippedCards.has(i) ? "showing answer, click to flip back" : "click to reveal answer"}`}
                    >
                      <div className="flashcard-inner">
                        <div className="flashcard-front">
                          <p className="font-medium text-zinc-900 text-sm leading-relaxed">
                            {card.front}
                          </p>
                          <p className="text-xs text-zinc-400 mt-auto pt-2">Click to reveal answer</p>
                        </div>
                        <div className="flashcard-back">
                          <p className="font-medium text-zinc-900 text-sm leading-relaxed">
                            {card.front}
                          </p>
                          <p className="text-xs text-zinc-600 mt-3 leading-relaxed border-t border-zinc-100 pt-3">
                            {card.back}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : generatingFlashcards ? (
                <div className="flex items-center gap-3 p-4 rounded-xl border border-zinc-200 bg-zinc-50">
                  <span className="spinner" style={{ width: 20, height: 20 }} />
                  <p className="text-sm text-zinc-500">Generating flashcards...</p>
                </div>
              ) : flashcardError ? (
                <div className="p-4 rounded-xl border border-red-200 bg-red-50 flex flex-col gap-3">
                  <p className="text-sm font-medium text-red-700">Generation failed</p>
                  <p className="text-xs text-red-600">{flashcardError}</p>
                  <button
                    onClick={generateFlashcards}
                    className="self-start text-xs font-medium text-white bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Try again
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 py-16 text-center">
                  <p className="text-sm text-zinc-400">Flashcards haven&apos;t been generated yet.</p>
                  <button
                    onClick={generateFlashcards}
                    className="text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
                  >
                    Generate Flashcards
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Quiz — 4 states: content / generating / error / empty */}
          {activeTab === "quiz" && (
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 mb-6">Quiz</h2>

              {session.quiz.length > 0 ? (
                <>
                  {quizPhase === "answering" && session.quiz[currentQ] && (
                    <div className="flex flex-col gap-4">
                      <p className="text-xs text-zinc-400">
                        Question {currentQ + 1} of {session.quiz.length}
                      </p>
                      <p className="text-base font-semibold text-zinc-900">
                        {session.quiz[currentQ].question}
                      </p>

                      <div className="flex flex-col gap-2">
                        {session.quiz[currentQ].options.map((option, i) => {
                          const answered = answers[currentQ] !== null;
                          const isSelected = answers[currentQ] === i;
                          const isCorrect = i === session.quiz[currentQ].answer_index;

                          let stateClass = "border-zinc-200 bg-white hover:border-zinc-400 hover:bg-zinc-50";
                          if (answered && isCorrect) stateClass = "border-green-500 bg-green-50";
                          else if (answered && isSelected) stateClass = "border-red-400 bg-red-50";

                          return (
                            <button
                              key={i}
                              onClick={() => selectAnswer(i)}
                              disabled={answered}
                              className={`block w-full text-left px-4 py-3 border rounded-xl text-sm text-zinc-900 transition-colors disabled:cursor-default ${stateClass}`}
                            >
                              {option}
                              {answered && isCorrect && (
                                <span className="ml-2 text-green-600">✓</span>
                              )}
                              {answered && isSelected && !isCorrect && (
                                <span className="ml-2 text-red-500">✗</span>
                              )}
                            </button>
                          );
                        })}
                      </div>

                      {answers[currentQ] !== null && (
                        <button
                          onClick={nextQuestion}
                          className="self-start text-sm text-zinc-500 hover:text-zinc-900 px-3 py-1.5 rounded-lg hover:bg-zinc-100 transition-colors"
                        >
                          {currentQ < session.quiz.length - 1 ? "Next question →" : "See results →"}
                        </button>
                      )}
                    </div>
                  )}

                  {quizPhase === "reviewing" && (
                    <div className="flex flex-col gap-6">
                      <div>
                        <h3 className="text-2xl font-bold text-zinc-900">
                          You scored {correctCount} / {session.quiz.length}
                        </h3>
                        <p className="text-sm text-zinc-500 mt-1">Review your answers below.</p>
                        <button
                          onClick={() => {
                            setTutorInput(`I just completed the quiz and scored ${correctCount} out of ${session.quiz.length}.`);
                            setActiveTab("tutor");
                          }}
                          className="mt-2 text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
                        >
                          Share results with tutor
                        </button>
                      </div>

                      <div className="flex flex-col gap-3">
                        {session.quiz.map((q, i) => {
                          const userAnswer = answers[i];
                          const correct = userAnswer === q.answer_index;
                          return (
                            <article
                              key={i}
                              className="border border-zinc-200 rounded-xl p-4"
                              style={{ borderLeft: `4px solid ${correct ? "#4ade80" : "#f87171"}` }}
                            >
                              <p className="font-semibold text-zinc-900 text-sm mb-2">
                                {i + 1}. {q.question}
                              </p>
                              <p className="text-xs text-green-700">
                                ✓ {q.options[q.answer_index]}
                              </p>
                              {!correct && userAnswer !== null && (
                                <p className="text-xs text-red-600 mt-0.5">
                                  ✗ Your answer: {q.options[userAnswer]}
                                </p>
                              )}
                            </article>
                          );
                        })}
                      </div>

                      <button
                        className="self-start text-sm text-zinc-500 hover:text-zinc-900 px-3 py-1.5 rounded-lg hover:bg-zinc-100 transition-colors"
                        onClick={() => {
                          setCurrentQ(0);
                          setAnswers(new Array(session!.quiz.length).fill(null));
                          setQuizPhase("answering");
                        }}
                      >
                        Retake quiz
                      </button>
                    </div>
                  )}
                </>
              ) : generatingQuiz ? (
                <div className="flex items-center gap-3 p-4 rounded-xl border border-zinc-200 bg-zinc-50">
                  <span className="spinner" style={{ width: 20, height: 20 }} />
                  <p className="text-sm text-zinc-500">Generating quiz...</p>
                </div>
              ) : quizError ? (
                <div className="p-4 rounded-xl border border-red-200 bg-red-50 flex flex-col gap-3">
                  <p className="text-sm font-medium text-red-700">Generation failed</p>
                  <p className="text-xs text-red-600">{quizError}</p>
                  <button
                    onClick={generateQuiz}
                    className="self-start text-xs font-medium text-white bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Try again
                  </button>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4 py-16 text-center">
                  <p className="text-sm text-zinc-400">Quiz hasn&apos;t been generated yet.</p>
                  <button
                    onClick={generateQuiz}
                    className="text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
                  >
                    Generate Quiz
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Tutor */}
          {activeTab === "tutor" && (
            <div data-testid="tutor-chat" className="flex flex-col flex-1 overflow-hidden">
              {/* Tutor header */}
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-100 shrink-0">
                <span className="text-xs text-zinc-400">
                  {tutorHistory.filter(m => m.content.trim() !== "").length} / {TUTOR_MAX_MESSAGES} messages
                </span>
                <button
                  onClick={resetTutorChat}
                  disabled={isTutorStreaming || tutorHistory.length === 0}
                  title="Reset tutor conversation"
                  className="text-zinc-400 hover:text-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
              </div>
              {/* Message list */}
              <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3 pb-16 md:pb-0">
                {tutorHistory.map((msg, i) => {
                  // Don't render empty assistant placeholders — the typing indicator handles that state
                  if (msg.role === "assistant" && msg.content === "") return null;
                  return (
                    <div
                      key={i}
                      className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      {msg.role === "user" ? (
                        <div className="max-w-[80%] rounded-2xl rounded-br-sm px-3 py-2 text-sm leading-relaxed bg-blue-600 text-white">
                          {msg.content}
                        </div>
                      ) : (
                        <div className="w-full max-w-[90%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm leading-relaxed bg-zinc-100 text-zinc-900">
                          <div className="prose prose-sm max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                          </div>
                          {/* Streaming cursor — shows while this is the active streaming message */}
                          {isTutorStreaming && i === tutorHistory.length - 1 && (
                            <div className="flex items-center gap-1 mt-1.5">
                              <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                              <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "75ms" }} />
                              <span className="w-1 h-1 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
                {/* Typing indicator — shown before first token arrives */}
                {isTutorStreaming && tutorHistory[tutorHistory.length - 1]?.content.trim() === "" && (
                  <div className="flex justify-start">
                    <div className="rounded-2xl rounded-bl-sm px-3 py-2 bg-zinc-100">
                      <div className="flex gap-1 items-center h-5">
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={tutorMessagesEndRef} />
              </div>

              {/* Input area */}
              <div className="border-t border-zinc-200 px-4 py-3 flex flex-col gap-2 bg-white">
                {tutorHistory.filter(m => m.content.trim() !== "").length >= TUTOR_MAX_MESSAGES ? (
                  <div className="flex items-center justify-between py-1">
                    <p className="text-xs text-zinc-400">Conversation limit reached.</p>
                    <button
                      onClick={resetTutorChat}
                      className="text-xs font-medium text-blue-600 hover:text-blue-700"
                    >
                      Start new conversation
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-2 items-end">
                    <textarea
                      ref={tutorTextareaRef}
                      rows={1}
                      value={tutorInput}
                      onChange={(e) => {
                        setTutorInput(e.target.value);
                        e.target.style.height = "auto";
                        e.target.style.height = `${e.target.scrollHeight}px`;
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          if (tutorInput.trim() && !isTutorStreaming) {
                            const msg = tutorInput;
                            setTutorInput("");
                            if (tutorTextareaRef.current) tutorTextareaRef.current.style.height = "auto";
                            sendTutorMessage(msg);
                          }
                        }
                      }}
                      disabled={isTutorStreaming || !session}
                      placeholder="Ask your tutor anything about this material..."
                      className="flex-1 resize-none rounded-xl border border-zinc-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 max-h-32 overflow-y-auto"
                    />
                    <button
                      onClick={() => {
                        if (tutorInput.trim() && !isTutorStreaming) {
                          const msg = tutorInput;
                          setTutorInput("");
                          if (tutorTextareaRef.current) tutorTextareaRef.current.style.height = "auto";
                          sendTutorMessage(msg);
                        }
                      }}
                      disabled={!tutorInput.trim() || isTutorStreaming || !session}
                      className="rounded-xl bg-blue-600 text-white px-3 py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
                    >
                      Send
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </main>

        {/* Mobile bottom tab bar — hidden on desktop */}
        <nav
          className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-zinc-100 flex z-50"
          style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          {(["notes", "flashcards", "quiz", "tutor"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 flex flex-col items-center justify-center py-2 gap-1 text-[0.6875rem] transition-colors min-h-[56px] ${
                activeTab === tab
                  ? "text-blue-600 font-semibold"
                  : "text-zinc-400"
              }`}
            >
              {TAB_ICONS[tab]}
              {TAB_LABELS[tab]}
            </button>
          ))}
        </nav>

      </div>

      {session && session.notes && (
        <>
          {/* Floating chat bubble — hidden while panel is open */}
          <button
            onClick={() => setChatOpen(true)}
            aria-label="Open chat"
            className={`fixed bottom-20 right-4 lg:bottom-6 lg:right-6 z-[60] w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-all duration-200 ${chatOpen ? "opacity-0 pointer-events-none" : "opacity-100"}`}
          >
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" />
            </svg>
          </button>

          {/* Sliding chat panel */}
          <div
            className={`fixed top-0 right-0 h-[calc(100vh-56px)] w-full lg:w-[360px] bg-white border-l border-zinc-200 shadow-xl z-[55] flex flex-col transition-transform duration-300 ${
              chatOpen ? "translate-x-0" : "translate-x-full"
            }`}
            style={{ top: "56px" }}
          >
            {/* Panel header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-100 shrink-0">
              <span className="text-sm font-semibold text-zinc-900">Ask about this session</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={resetChat}
                  aria-label="Reset chat"
                  title="Start a new conversation"
                  className="text-zinc-400 hover:text-zinc-600 transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                </button>
                <button
                  onClick={() => setChatOpen(false)}
                  aria-label="Close chat"
                  className="text-zinc-400 hover:text-zinc-600 transition-colors"
                >
                  <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Message list */}
            <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3">
              {/* Persona-adapted intro — always shown as first assistant bubble */}
              {session.chat_intro && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm leading-relaxed bg-zinc-100 text-zinc-900">
                    {session.chat_intro}
                  </div>
                </div>
              )}
              {chatHistory.length === 0 && !session.chat_intro && (
                <p className="text-xs text-zinc-400 text-center mt-8">
                  Ask anything about the session content.
                </p>
              )}
              {chatHistory.map((msg, i) => (
                <div
                  key={i}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white rounded-br-sm"
                        : "bg-zinc-100 text-zinc-900 rounded-bl-sm"
                    }`}
                  >
                    {msg.content}
                  </div>
                </div>
              ))}
              {/* Only show typing indicator if the last message is an empty assistant message and we're streaming */}
              {isStreaming && chatHistory.length > 0 && chatHistory[chatHistory.length - 1]?.role === "assistant" && chatHistory[chatHistory.length - 1]?.content === "" && (
                <div className="flex justify-start">
                  <div className="max-w-[80%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm leading-relaxed bg-zinc-100 text-zinc-900">
                    <span className="inline-flex gap-0.5 items-center h-4">
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                      <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
            {chatHistory.length >= MAX_MESSAGES ? (
              <div className="shrink-0 px-4 py-4 border-t border-zinc-100 text-center">
                <p className="text-xs text-zinc-500 mb-2">Conversation limit reached.</p>
                <button
                  onClick={resetChat}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium underline underline-offset-2"
                >
                  Reset to start a new conversation
                </button>
              </div>
            ) : (
              <div className="shrink-0 px-3 py-3 border-t border-zinc-100 flex gap-2 items-end">
                <textarea
                  ref={textareaRef}
                  value={chatInput}
                  onChange={(e) => {
                    setChatInput(e.target.value);
                    const el = e.target;
                    el.style.height = "auto";
                    el.style.height = `${el.scrollHeight}px`;
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  disabled={isStreaming}
                  placeholder="Ask a question..."
                  rows={1}
                  className="flex-1 resize-none rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none focus:border-blue-400 focus:bg-white transition-colors disabled:opacity-50"
                  style={{ maxHeight: "120px" }}
                />
                <button
                  onClick={sendMessage}
                  disabled={isStreaming || !chatInput.trim()}
                  aria-label="Send"
                  className="shrink-0 w-9 h-9 rounded-xl bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed text-white flex items-center justify-center transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M22 2L11 13" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M22 2L15 22 11 13 2 9l20-7z" />
                  </svg>
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
