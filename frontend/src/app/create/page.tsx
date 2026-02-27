"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { TutoringType, SessionRequest } from "@/types/session";

type InputMode = "url" | "topic";

const TUTORING_MODES: { id: TutoringType; label: string; description: string }[] = [
  { id: "micro_learning", label: "Micro Learning", description: "Short, punchy bullets. Just the essentials, fast." },
  { id: "teaching_a_kid", label: "Teaching a Kid", description: "Plain language and everyday analogies. No jargon." },
  { id: "advanced", label: "Advanced", description: "Full technical depth for graduate-level understanding." },
];

const ERROR_MESSAGES: Record<string, { top: string; pointer: string }> = {
  paywall: { top: "We couldn't read that page", pointer: "This looks like a paywalled article. Try pasting the article text below." },
  invalid_url: { top: "We couldn't read that page", pointer: "The URL doesn't look valid. Check it and try again, or paste the article text." },
  empty: { top: "We couldn't read that page", pointer: "The page loaded but didn't have enough readable text. You can paste the content below." },
  unreachable: { top: "We couldn't reach that page", pointer: "The site may be down or blocked. Paste the article text below to continue." },
};

const inputClass =
  "w-full px-3 py-2.5 border border-zinc-200 rounded-lg bg-white text-zinc-900 text-sm placeholder:text-zinc-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 transition-colors font-[inherit]";

function CreateForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const errorParam = searchParams.get("error");
  const tutoringTypeParam = searchParams.get("tutoring_type") as TutoringType | null;
  const focusPromptParam = searchParams.get("focus_prompt") ?? "";
  const inputModeParam = (searchParams.get("input_mode") as InputMode | null) ?? "url";

  const [selectedMode, setSelectedMode] = useState<TutoringType | null>(
    errorParam && tutoringTypeParam ? tutoringTypeParam : null
  );
  const [inputMode, setInputMode] = useState<InputMode>(errorParam ? inputModeParam : "url");
  const [url, setUrl] = useState("");
  const [topicDescription, setTopicDescription] = useState("");
  const [focusPrompt, setFocusPrompt] = useState(errorParam ? focusPromptParam : "");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorKind, setErrorKind] = useState<string | null>(errorParam);
  const [pasteText, setPasteText] = useState("");

  const errorMessages = errorKind ? ERROR_MESSAGES[errorKind] ?? ERROR_MESSAGES.empty : null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedMode) return;
    setIsSubmitting(true);
    setErrorKind(null);

    const payload: SessionRequest = {
      tutoring_type: selectedMode,
      focus_prompt: focusPrompt || undefined,
      ...(inputMode === "topic"
        ? { topic_description: topicDescription }
        : pasteText
        ? { paste_text: pasteText }
        : { url }),
    };

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Server error");
      const { session_id } = await res.json();
      router.push(
        `/loading?session_id=${session_id}&tutoring_type=${selectedMode}&focus_prompt=${encodeURIComponent(focusPrompt)}&input_mode=${inputMode}`
      );
    } catch {
      setUrl("");
      setTopicDescription("");
      setErrorKind("empty");
      setIsSubmitting(false);
    }
  }

  return (
    <main className="max-w-xl mx-auto px-5 pt-12 pb-12">
      <h1 className="text-2xl font-bold text-zinc-900 mb-8">
        Create a study session
      </h1>

      <form onSubmit={handleSubmit} className="flex flex-col gap-6">

        {/* Tutoring mode cards */}
        <fieldset className="border-none p-0 m-0">
          <legend className="text-sm font-medium text-zinc-500 mb-3">
            How do you want to learn?
          </legend>
          <div className="flex flex-col gap-2">
            {TUTORING_MODES.map((mode) => (
              <label key={mode.id} className="cursor-pointer">
                <input
                  type="radio"
                  name="tutoring_mode"
                  value={mode.id}
                  checked={selectedMode === mode.id}
                  onChange={() => setSelectedMode(mode.id)}
                  className="sr-only"
                />
                <div
                  className={`border-2 rounded-xl p-4 transition-colors ${
                    selectedMode === mode.id
                      ? "border-blue-600 bg-blue-50"
                      : "border-zinc-200 hover:border-zinc-300"
                  }`}
                >
                  <p className="font-semibold text-zinc-900 text-sm mb-0.5">
                    {mode.label}
                  </p>
                  <p className="text-xs text-zinc-500">{mode.description}</p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        {/* Input mode toggle */}
        <div className="flex rounded-lg border border-zinc-200 overflow-hidden self-start">
          <button
            type="button"
            onClick={() => { setInputMode("url"); setTopicDescription(""); }}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              inputMode === "url" ? "bg-zinc-900 text-white" : "bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            Article URL
          </button>
          <button
            type="button"
            onClick={() => { setInputMode("topic"); setUrl(""); }}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              inputMode === "topic" ? "bg-zinc-900 text-white" : "bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            Topic description
          </button>
        </div>

        {/* URL input */}
        {inputMode === "url" && !pasteText && (
          <div className="flex flex-col gap-2">
            <label htmlFor="url" className="text-sm font-medium text-zinc-900">
              Article or doc URL
            </label>
            <input
              id="url"
              type="url"
              className={inputClass}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              required={inputMode === "url" && !pasteText}
            />
          </div>
        )}

        {/* Topic description input */}
        {inputMode === "topic" && !pasteText && (
          <div className="flex flex-col gap-2">
            <label htmlFor="topic_description" className="text-sm font-medium text-zinc-900">
              What do you want to learn about?
            </label>
            <textarea
              id="topic_description"
              className={inputClass}
              value={topicDescription}
              onChange={(e) => setTopicDescription(e.target.value)}
              placeholder="Describe a topic you want to learn about… (e.g. 'How transformer models work in NLP', 'The causes of World War I', 'Basics of Kubernetes networking')"
              rows={3}
              style={{ resize: "vertical" }}
            />
            {topicDescription.length > 0 && topicDescription.length < 30 && (
              <p className="text-xs text-red-500">
                Please describe your topic in a bit more detail (at least a few words).
              </p>
            )}
          </div>
        )}

        {/* Inline error + paste fallback — URL mode only; topic mode uses research agent, not paste */}
        {errorMessages && inputMode !== "topic" && (
          <div
            className="flex flex-col gap-3 p-4 rounded-xl border border-red-200 bg-red-50"
            role="alert"
          >
            <p className="font-semibold text-sm text-red-700">{errorMessages.top}</p>
            <p className="text-xs text-red-600">{errorMessages.pointer}</p>
            <label htmlFor="paste_text" className="text-sm font-medium text-zinc-900">
              Paste the article text instead
            </label>
            <textarea
              id="paste_text"
              className={inputClass}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste the full article text here (at least a few paragraphs)..."
              rows={8}
              minLength={200}
              maxLength={50000}
              style={{ resize: "vertical" }}
            />
            {pasteText.length > 0 && pasteText.length < 200 && (
              <p className="text-xs text-red-500">
                Please paste at least a few paragraphs for best results.
              </p>
            )}
          </div>
        )}

        {/* Focus prompt */}
        <div className="flex flex-col gap-2">
          <label htmlFor="focus_prompt" className="text-sm font-medium text-zinc-900">
            What do you want to focus on?{" "}
            <span className="text-zinc-400 font-normal">(optional)</span>
          </label>
          <input
            id="focus_prompt"
            type="text"
            className={inputClass}
            value={focusPrompt}
            onChange={(e) => setFocusPrompt(e.target.value)}
            placeholder="e.g. 'key algorithms', 'historical causes', 'main arguments'"
          />
        </div>

        <button
          type="submit"
          className="self-start px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          disabled={
            !selectedMode ||
            isSubmitting ||
            (pasteText.length > 0 && pasteText.length < 200) ||
            (inputMode === "topic" && !pasteText && topicDescription.length < 30)
          }
        >
          {isSubmitting ? "Starting..." : "Generate my study session →"}
        </button>
      </form>

      <div className="mt-8">
        <Link
          href="/"
          className="text-sm text-zinc-500 hover:text-zinc-900 transition-colors"
        >
          ← Back
        </Link>
      </div>
    </main>
  );
}

export default function CreatePage() {
  return (
    <Suspense>
      <CreateForm />
    </Suspense>
  );
}
