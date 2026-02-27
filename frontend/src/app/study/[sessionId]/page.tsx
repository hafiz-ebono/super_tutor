"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { SessionResult, TutoringType } from "@/types/session";

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

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;
    fetch(`${apiUrl}/sessions/${sessionId}`)
      .then((res) => {
        if (!res.ok) throw new Error("Session not found");
        return res.json();
      })
      .then((data: SessionResult) => {
        setSession(data);
        setAnswers(new Array(data.quiz.length).fill(null));
        setLoading(false);
      })
      .catch((e) => {
        setError(e.message);
        setLoading(false);
      });
  }, [sessionId]);

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
          Session not found.{" "}
          <Link href="/create" className="text-blue-600 hover:underline">
            Start a new session
          </Link>
        </p>
      </main>
    );
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

  const correctCount = answers.filter((a, i) => a === session!.quiz[i]?.answer_index).length;

  return (
    <div className="flex" style={{ minHeight: "calc(100vh - 56px)" }}>

      {/* Desktop sidebar — hidden on mobile */}
      <aside className="hidden md:flex w-52 shrink-0 flex-col border-r border-zinc-100 px-3 py-5">
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
        <div className="md:hidden flex flex-col gap-1.5 px-5 py-3 border-b border-zinc-100">
          <p className="font-semibold text-zinc-900 text-sm leading-snug truncate">
            {session.source_title}
          </p>
          <span className="self-start inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium bg-zinc-100 text-zinc-600">
            {MODE_LABELS[session.tutoring_type]}
          </span>
        </div>

        {/* Main content */}
        <main className="flex-1 px-6 py-8 max-w-3xl md:pb-8 pb-24">

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

          {/* Flashcards */}
          {activeTab === "flashcards" && (
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 mb-6">Flashcards</h2>
              {session.errors?.flashcards ? (
                <div className="p-4 rounded-xl border border-red-200 bg-red-50">
                  <p className="text-sm font-medium text-red-700 mb-1">Flashcards unavailable</p>
                  <p className="text-xs text-red-600">{session.errors.flashcards}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {session.flashcards.map((card, i) => (
                    <article
                      key={i}
                      className="border border-zinc-200 rounded-xl p-5 bg-white min-h-[100px] flex flex-col justify-between"
                    >
                      <p className="font-medium text-zinc-900 text-sm leading-relaxed">
                        {card.front}
                      </p>
                      <p className="text-xs text-zinc-400 mt-3 leading-relaxed">
                        {card.back}
                      </p>
                    </article>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Quiz */}
          {activeTab === "quiz" && (
            <div>
              <h2 className="text-xl font-semibold text-zinc-900 mb-6">Quiz</h2>

              {session.errors?.quiz && (
                <div className="p-4 rounded-xl border border-red-200 bg-red-50 mb-4">
                  <p className="text-sm font-medium text-red-700 mb-1">Quiz unavailable</p>
                  <p className="text-xs text-red-600">{session.errors.quiz}</p>
                </div>
              )}

              {!session.errors?.quiz && quizPhase === "answering" && session.quiz[currentQ] && (
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

              {!session.errors?.quiz && quizPhase === "reviewing" && (
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
            </div>
          )}
        </main>

        {/* Mobile bottom tab bar — hidden on desktop */}
        <nav
          className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-zinc-100 flex z-50"
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
    </div>
  );
}
