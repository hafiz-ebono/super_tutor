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
      <main className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <span className="spinner" />
      </main>
    );
  }

  if (error || !session) {
    return (
      <main className="flex items-center justify-center" style={{ minHeight: "100vh" }}>
        <p style={{ color: "var(--muted-foreground)" }}>
          Session not found.{" "}
          <Link href="/create" style={{ color: "var(--primary)" }}>Start a new session</Link>
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
    <div className="flex" style={{ minHeight: "100vh" }}>

      {/* Sidebar */}
      <aside className="study-sidebar">
        <div style={{ marginBottom: "var(--space-6)" }}>
          <p style={{ fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)", fontSize: "var(--text-2)", lineHeight: "1.4" }}>
            {session.source_title}
          </p>
          <span className="badge" style={{ fontSize: "var(--text-1)" }}>
            {MODE_LABELS[session.tutoring_type]}
          </span>
        </div>

        <nav className="vstack" style={{ gap: "var(--space-1)" }}>
          {(["notes", "flashcards", "quiz"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`nav-link${activeTab === tab ? " nav-link-active" : ""}`}
            >
              {tab}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: "auto" }}>
          <Link href="/create" className="nav-link" style={{ fontSize: "var(--text-1)" }}>
            + New session
          </Link>
        </div>
      </aside>

      {/* Content */}
      <main style={{ flex: 1, padding: "var(--space-8)", maxWidth: "780px" }}>

        {/* Notes */}
        {activeTab === "notes" && (
          <article className="prose">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.notes}</ReactMarkdown>
          </article>
        )}

        {/* Flashcards */}
        {activeTab === "flashcards" && (
          <div>
            <h2 style={{ fontSize: "var(--text-4)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-6)" }}>
              Flashcards
            </h2>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "var(--space-4)" }}>
              {session.flashcards.map((card, i) => (
                <article key={i} className="card" style={{ padding: "var(--space-5)", minHeight: "120px" }}>
                  <p style={{ fontWeight: "var(--font-medium)", fontSize: "var(--text-2)" }}>{card.front}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {/* Quiz */}
        {activeTab === "quiz" && (
          <div>
            <h2 style={{ fontSize: "var(--text-4)", fontWeight: "var(--font-semibold)", marginBottom: "var(--space-6)" }}>
              Quiz
            </h2>

            {quizPhase === "answering" && session.quiz[currentQ] && (
              <div className="vstack" style={{ gap: "var(--space-4)" }}>
                <p style={{ fontSize: "var(--text-1)", color: "var(--muted-foreground)" }}>
                  Question {currentQ + 1} of {session.quiz.length}
                </p>
                <p style={{ fontSize: "var(--text-3)", fontWeight: "var(--font-semibold)" }}>
                  {session.quiz[currentQ].question}
                </p>

                <div className="vstack" style={{ gap: "var(--space-2)" }}>
                  {session.quiz[currentQ].options.map((option, i) => {
                    const answered = answers[currentQ] !== null;
                    const isSelected = answers[currentQ] === i;
                    const isCorrect = i === session.quiz[currentQ].answer_index;
                    let extraClass = "";
                    if (answered && isCorrect) extraClass = " quiz-option-correct";
                    else if (answered && isSelected) extraClass = " quiz-option-wrong";

                    return (
                      <button
                        key={i}
                        onClick={() => selectAnswer(i)}
                        disabled={answered}
                        className={`quiz-option${extraClass}`}
                      >
                        {option}
                        {answered && isCorrect && " ✓"}
                        {answered && isSelected && !isCorrect && " ✗"}
                      </button>
                    );
                  })}
                </div>

                {answers[currentQ] !== null && (
                  <button onClick={nextQuestion} className="btn btn-ghost" style={{ alignSelf: "flex-start" }}>
                    {currentQ < session.quiz.length - 1 ? "Next question →" : "See results →"}
                  </button>
                )}
              </div>
            )}

            {quizPhase === "reviewing" && (
              <div className="vstack" style={{ gap: "var(--space-6)" }}>
                <div>
                  <h3 style={{ fontSize: "var(--text-4)", fontWeight: "var(--font-bold)" }}>
                    You scored {correctCount} / {session.quiz.length}
                  </h3>
                  <p style={{ color: "var(--muted-foreground)", marginTop: "var(--space-2)" }}>
                    Review your answers below.
                  </p>
                </div>

                <div className="vstack" style={{ gap: "var(--space-4)" }}>
                  {session.quiz.map((q, i) => {
                    const userAnswer = answers[i];
                    const correct = userAnswer === q.answer_index;
                    return (
                      <article
                        key={i}
                        className="card"
                        style={{
                          padding: "var(--space-4)",
                          borderLeft: `4px solid var(${correct ? "--success" : "--danger"})`,
                        }}
                      >
                        <p style={{ fontWeight: "var(--font-semibold)", marginBottom: "var(--space-2)" }}>
                          {i + 1}. {q.question}
                        </p>
                        <p style={{ fontSize: "var(--text-1)", color: "var(--success-foreground)" }}>
                          ✓ {q.options[q.answer_index]}
                        </p>
                        {!correct && userAnswer !== null && (
                          <p style={{ fontSize: "var(--text-1)", color: "var(--danger-foreground)", marginTop: "var(--space-1)" }}>
                            ✗ Your answer: {q.options[userAnswer]}
                          </p>
                        )}
                      </article>
                    );
                  })}
                </div>

                <button
                  className="btn btn-ghost"
                  style={{ alignSelf: "flex-start" }}
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
    </div>
  );
}
