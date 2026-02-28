"use client";
import Link from "next/link";
import { useRecentSessions } from "@/app/hooks/useRecentSessions";

const FEATURES = [
  {
    title: "Micro Learning",
    body: "Short, punchy bullets. Just the essentials, fast.",
    icon: "⚡",
  },
  {
    title: "Teaching a Kid",
    body: "Plain language and everyday analogies. No jargon.",
    icon: "🎯",
  },
  {
    title: "Advanced",
    body: "Full technical depth for graduate-level understanding.",
    icon: "🎓",
  },
];

export default function LandingPage() {
  const { sessions } = useRecentSessions();

  return (
    <main>
      {/* Hero */}
      <section className="max-w-3xl mx-auto px-5 pt-20 pb-20 flex flex-col items-center text-center">
        <p className="text-xs font-semibold text-blue-600 uppercase tracking-widest mb-3">
          AI-powered study companion
        </p>
        <h1 className="text-4xl sm:text-5xl font-bold text-zinc-900 leading-tight tracking-tight max-w-xl">
          Turn any article into a complete study session
        </h1>
        <p className="text-base text-zinc-500 max-w-md mt-5 leading-relaxed">
          Super Tutor transforms any article or doc URL into structured notes,
          interactive flashcards, and a quiz — tailored to your learning style,
          ready in under a minute.
        </p>
        <Link
          href="/create"
          className="mt-8 inline-flex items-center px-6 py-3 bg-blue-600 text-white font-medium rounded-xl hover:bg-blue-700 transition-colors"
        >
          Start studying →
        </Link>
      </section>

      {/* Feature cards */}
      <section className="max-w-3xl mx-auto px-5 pt-12 pb-16 border-t border-zinc-100">
        <h2 className="text-center text-xl font-semibold text-zinc-900 mb-8">
          Three ways to learn
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {FEATURES.map((card) => (
            <article
              key={card.title}
              className="border border-zinc-200 rounded-xl p-6 bg-white"
            >
              <div className="text-2xl mb-3">{card.icon}</div>
              <h3 className="font-semibold text-zinc-900 mb-1 text-sm">
                {card.title}
              </h3>
              <p className="text-sm text-zinc-500 leading-relaxed">{card.body}</p>
            </article>
          ))}
        </div>
      </section>

      {/* Recent sessions */}
      {sessions.length > 0 && (
        <section className="max-w-3xl mx-auto px-5 pt-8 pb-16 border-t border-zinc-100">
          <h2 className="text-sm font-semibold text-zinc-500 uppercase tracking-wide mb-4">
            Recent sessions
          </h2>
          <div className="flex flex-col gap-2">
            {sessions.map((s) => (
              <Link
                key={s.session_id}
                href={`/study/${s.session_id}`}
                className="flex items-center justify-between px-4 py-3 border border-zinc-200 rounded-xl bg-white hover:border-zinc-300 hover:bg-zinc-50 transition-colors group"
              >
                <span className="text-sm font-medium text-zinc-900 truncate max-w-[70%]">
                  {s.source_title}
                </span>
                <span className="text-xs text-zinc-400 shrink-0 ml-3">
                  {new Date(s.saved_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
