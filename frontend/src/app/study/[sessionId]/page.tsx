"use client";
import { useEffect, useState, useRef } from "react";
import { useParams } from "next/navigation";
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

type Tab = "notes" | "flashcards" | "quiz";

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
};

export default function StudyPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

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

  const [chatOpen, setChatOpen] = useState(false);
  const [chatHistory, setChatHistory] = useState<{ role: "user" | "assistant"; content: string }[]>(() => {
    try {
      const stored = localStorage.getItem(`chat:${sessionId}`);
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });
  const [chatInput, setChatInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function toggleFlip(index: number) {
    setFlippedCards((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  // Persist chat history to localStorage whenever it changes
  useEffect(() => {
    if (chatHistory.length > 0) {
      localStorage.setItem(`chat:${sessionId}`, JSON.stringify(chatHistory));
    }
  }, [chatHistory, sessionId]);

  // Auto-scroll chat to bottom when chatHistory changes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  // Auto-focus textarea when chat panel opens
  useEffect(() => {
    if (chatOpen) {
      // Small timeout to allow panel transition to start before focusing
      const t = setTimeout(() => textareaRef.current?.focus(), 50);
      return () => clearTimeout(t);
    }
  }, [chatOpen]);

  // Load session from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(`session:${sessionId}`);
    if (!stored) {
      setError("Session not found on this device.");
      setLoading(false);
      return;
    }
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
  }, [sessionId]);

  // Persist a partial update back to localStorage and state
  function updateSession(patch: Partial<SessionResult>) {
    setSession((prev) => {
      if (!prev) return prev;
      const updated = { ...prev, ...patch };
      localStorage.setItem(`session:${sessionId}`, JSON.stringify(updated));
      return updated;
    });
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
          body: JSON.stringify({ notes: session.notes, tutoring_type: session.tutoring_type }),
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
          body: JSON.stringify({ notes: session.notes, tutoring_type: session.tutoring_type }),
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
    setChatHistory([]);
    localStorage.removeItem(`chat:${sessionId}`);
  }

  async function sendMessage() {
    if (!session || !chatInput.trim() || isStreaming) return;
    const userMessage = chatInput.trim();
    setChatInput("");
    // Optimistically add user turn
    const history = [...chatHistory, { role: "user" as const, content: userMessage }];
    setChatHistory(history);
    setIsStreaming(true);

    // Add empty assistant placeholder
    setChatHistory((prev) => [...prev, { role: "assistant" as const, content: "" }]);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMessage,
          notes: session.notes,
          tutoring_type: session.tutoring_type,
          // Send last 6 prior turns (client-side cap; backend is stateless)
          history: history.slice(0, -1).slice(-6),
        }),
      });

      if (!res.ok || !res.body) throw new Error("Stream request failed");

      const reader = res.body.getReader();
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
            }
          } catch {
            // Ignore non-JSON data lines (e.g. event: done line)
          }
        }
      }
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
      setIsStreaming(false);
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
          {(["notes", "flashcards", "quiz"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex items-center gap-2.5 w-full text-left px-2 py-2 rounded-lg text-sm capitalize transition-colors ${
                activeTab === tab
                  ? "bg-zinc-100 text-zinc-900 font-medium"
                  : "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900"
              }`}
            >
              {TAB_ICONS[tab]}
              {tab}
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
        <main className={`flex-1 px-6 py-8 md:pb-8 pb-24 transition-all duration-300 ${chatOpen ? "lg:mr-[360px]" : ""}`}>

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
                    {session.sources.map((src, i) => (
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
        </main>

        {/* Mobile bottom tab bar — hidden on desktop */}
        <nav
          className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-zinc-100 flex z-50"
          style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
        >
          {(["notes", "flashcards", "quiz"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 flex flex-col items-center justify-center py-2 gap-1 text-[0.6875rem] capitalize transition-colors min-h-[56px] ${
                activeTab === tab
                  ? "text-blue-600 font-semibold"
                  : "text-zinc-400"
              }`}
            >
              {TAB_ICONS[tab]}
              {tab}
            </button>
          ))}
        </nav>

      </div>

      {session && session.notes && (
        <>
          {/* Floating chat bubble */}
          <button
            onClick={() => setChatOpen((o) => !o)}
            aria-label="Open chat"
            className="fixed bottom-20 right-4 lg:bottom-6 lg:right-6 z-[60] w-12 h-12 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg flex items-center justify-center transition-colors"
          >
            {chatOpen ? (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 10h.01M12 10h.01M16 10h.01M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10z" />
              </svg>
            )}
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
                  disabled={chatHistory.length === 0 || isStreaming}
                  aria-label="Reset chat"
                  title="Clear chat history"
                  className="text-zinc-400 hover:text-zinc-600 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M1 4v6h6M23 20v-6h-6" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
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
              {chatHistory.length === 0 && (
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
                    {msg.content || (
                      <span className="inline-flex gap-0.5 items-center h-4">
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                        <span className="w-1.5 h-1.5 rounded-full bg-zinc-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                      </span>
                    )}
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>

            {/* Input area */}
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
          </div>
        </>
      )}
    </div>
  );
}
