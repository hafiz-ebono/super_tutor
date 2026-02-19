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

  // Quiz state
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

  if (loading) return <main><p>Loading your session...</p></main>;
  if (error || !session) return (
    <main>
      <p>Session not found. <Link href="/create">Start a new session</Link></p>
    </main>
  );

  // Quiz helpers
  function selectAnswer(optionIndex: number) {
    if (answers[currentQ] !== null) return; // already answered
    const newAnswers = [...answers];
    newAnswers[currentQ] = optionIndex;
    setAnswers(newAnswers);
  }

  function nextQuestion() {
    if (currentQ < session!.quiz.length - 1) {
      setCurrentQ((q) => q + 1);
    } else {
      setQuizPhase("reviewing");
    }
  }

  const correctCount = answers.filter(
    (a, i) => a === session!.quiz[i]?.answer_index
  ).length;

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>

      {/* Left sidebar */}
      <aside
        style={{
          width: "240px",
          flexShrink: 0,
          borderRight: "1px solid rgba(0,0,0,0.1)",
          padding: "1.5rem 1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        <div style={{ marginBottom: "1rem" }}>
          <p style={{ fontWeight: "bold", marginBottom: "0.25rem" }}>{session.source_title}</p>
          <p style={{ fontSize: "0.75rem", opacity: 0.6 }}>
            {MODE_LABELS[session.tutoring_type]}
          </p>
        </div>

        <nav>
          {(["notes", "flashcards", "quiz"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "0.5rem 0.75rem",
                background: activeTab === tab ? "rgba(0,0,0,0.06)" : "transparent",
                border: "none",
                cursor: "pointer",
                borderRadius: "4px",
                textTransform: "capitalize",
                fontWeight: activeTab === tab ? "bold" : "normal",
              }}
            >
              {tab}
            </button>
          ))}
        </nav>

        <div style={{ marginTop: "auto" }}>
          <Link href="/create" style={{ fontSize: "0.875rem", opacity: 0.7 }}>
            + New session
          </Link>
        </div>
      </aside>

      {/* Main content area */}
      <main style={{ flex: 1, padding: "2rem", maxWidth: "800px" }}>

        {/* Notes panel */}
        {activeTab === "notes" && (
          <article>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{session.notes}</ReactMarkdown>
          </article>
        )}

        {/* Flashcards panel */}
        {activeTab === "flashcards" && (
          <div>
            <h2>Flashcards</h2>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
                gap: "1rem",
              }}
            >
              {session.flashcards.map((card, i) => (
                <article
                  key={i}
                  style={{
                    border: "1px solid rgba(0,0,0,0.12)",
                    borderRadius: "8px",
                    padding: "1.25rem",
                    minHeight: "120px",
                  }}
                >
                  <p style={{ fontWeight: "bold" }}>{card.front}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {/* Quiz panel */}
        {activeTab === "quiz" && (
          <div>
            <h2>Quiz</h2>

            {quizPhase === "answering" && session.quiz[currentQ] && (
              <div>
                <p style={{ opacity: 0.5, fontSize: "0.875rem" }}>
                  Question {currentQ + 1} of {session.quiz.length}
                </p>
                <p style={{ fontWeight: "bold", fontSize: "1.1rem", margin: "1rem 0" }}>
                  {session.quiz[currentQ].question}
                </p>

                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {session.quiz[currentQ].options.map((option, i) => {
                    const answered = answers[currentQ] !== null;
                    const isSelected = answers[currentQ] === i;
                    const isCorrect = i === session.quiz[currentQ].answer_index;
                    const showFeedback = answered;

                    let feedbackStyle: React.CSSProperties = {};
                    if (showFeedback) {
                      if (isCorrect) feedbackStyle = { background: "rgba(0,200,0,0.12)", borderColor: "green" };
                      else if (isSelected) feedbackStyle = { background: "rgba(200,0,0,0.1)", borderColor: "red" };
                    }

                    return (
                      <button
                        key={i}
                        onClick={() => selectAnswer(i)}
                        disabled={answered}
                        style={{
                          textAlign: "left",
                          padding: "0.75rem 1rem",
                          border: "1px solid rgba(0,0,0,0.2)",
                          borderRadius: "6px",
                          cursor: answered ? "default" : "pointer",
                          background: "transparent",
                          ...feedbackStyle,
                        }}
                      >
                        {option}
                        {showFeedback && isCorrect && " \u2713"}
                        {showFeedback && isSelected && !isCorrect && " \u2717"}
                      </button>
                    );
                  })}
                </div>

                {answers[currentQ] !== null && (
                  <button
                    onClick={nextQuestion}
                    style={{ marginTop: "1rem" }}
                  >
                    {currentQ < session.quiz.length - 1 ? "Next question \u2192" : "See results \u2192"}
                  </button>
                )}
              </div>
            )}

            {/* Score summary + review */}
            {quizPhase === "reviewing" && (
              <div>
                <h3>
                  You scored {correctCount} / {session.quiz.length}
                </h3>
                <p style={{ opacity: 0.6, marginBottom: "2rem" }}>
                  Review your answers below.
                </p>

                {session.quiz.map((q, i) => {
                  const userAnswer = answers[i];
                  const correct = userAnswer === q.answer_index;
                  return (
                    <article
                      key={i}
                      style={{
                        marginBottom: "1.5rem",
                        padding: "1rem",
                        border: "1px solid rgba(0,0,0,0.1)",
                        borderRadius: "8px",
                        borderLeft: `4px solid ${correct ? "green" : "red"}`,
                      }}
                    >
                      <p style={{ fontWeight: "bold" }}>
                        {i + 1}. {q.question}
                      </p>
                      <p style={{ color: "green" }}>Correct: {q.options[q.answer_index]}</p>
                      {!correct && userAnswer !== null && (
                        <p style={{ color: "red" }}>Your answer: {q.options[userAnswer]}</p>
                      )}
                    </article>
                  );
                })}

                <button onClick={() => { setCurrentQ(0); setAnswers(new Array(session!.quiz.length).fill(null)); setQuizPhase("answering"); }}>
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
