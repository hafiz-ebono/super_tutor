"use client";
import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { TutoringType, SessionRequest } from "@/types/session";

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

export default function CreatePage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const errorParam = searchParams.get("error");
  const tutoringTypeParam = searchParams.get("tutoring_type") as TutoringType | null;
  const focusPromptParam = searchParams.get("focus_prompt") ?? "";

  const [selectedMode, setSelectedMode] = useState<TutoringType | null>(
    errorParam && tutoringTypeParam ? tutoringTypeParam : null
  );
  const [url, setUrl] = useState("");
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
      ...(pasteText ? { paste_text: pasteText } : { url }),
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
        `/loading?session_id=${session_id}&tutoring_type=${selectedMode}&focus_prompt=${encodeURIComponent(focusPrompt)}`
      );
    } catch {
      setUrl("");
      setErrorKind("empty");
      setIsSubmitting(false);
    }
  }

  return (
    <main className="container" style={{ maxWidth: "640px", paddingTop: "var(--space-12)", paddingBottom: "var(--space-12)" }}>
      <h1 style={{ fontSize: "var(--text-5)", fontWeight: "var(--font-bold)", marginBottom: "var(--space-8)" }}>
        Create a study session
      </h1>

      <form onSubmit={handleSubmit} className="vstack" style={{ gap: "var(--space-6)" }}>

        {/* Tutoring mode cards */}
        <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
          <legend style={{ fontSize: "var(--text-2)", fontWeight: "var(--font-medium)", marginBottom: "var(--space-3)", color: "var(--muted-foreground)" }}>
            How do you want to learn?
          </legend>
          <div className="vstack" style={{ gap: "var(--space-2)" }}>
            {TUTORING_MODES.map((mode) => (
              <label key={mode.id} style={{ cursor: "pointer" }}>
                <input
                  type="radio"
                  name="tutoring_mode"
                  value={mode.id}
                  checked={selectedMode === mode.id}
                  onChange={() => setSelectedMode(mode.id)}
                  style={{ display: "none" }}
                />
                <div className="mode-card" aria-selected={selectedMode === mode.id}>
                  <p style={{ fontWeight: "var(--font-semibold)", marginBottom: "var(--space-1)", fontSize: "var(--text-2)" }}>
                    {mode.label}
                  </p>
                  <p style={{ fontSize: "var(--text-1)", color: "var(--muted-foreground)" }}>
                    {mode.description}
                  </p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        {/* URL input */}
        {!pasteText && (
          <div className="vstack" style={{ gap: "var(--space-2)" }}>
            <label htmlFor="url" style={{ fontSize: "var(--text-2)", fontWeight: "var(--font-medium)" }}>
              Article or doc URL
            </label>
            <input
              id="url"
              type="url"
              className="input-field"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://..."
              required={!pasteText}
            />
          </div>
        )}

        {/* Inline error + paste fallback */}
        {errorMessages && (
          <div className="alert-danger vstack" style={{ gap: "var(--space-3)" }} role="alert">
            <p style={{ fontWeight: "var(--font-semibold)", fontSize: "var(--text-2)" }}>{errorMessages.top}</p>
            <p style={{ fontSize: "var(--text-1)" }}>{errorMessages.pointer}</p>
            <label htmlFor="paste_text" style={{ fontSize: "var(--text-2)", fontWeight: "var(--font-medium)" }}>
              Paste the article text instead
            </label>
            <textarea
              id="paste_text"
              className="input-field"
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder="Paste the full article text here (at least a few paragraphs)..."
              rows={8}
              minLength={200}
              maxLength={50000}
              style={{ resize: "vertical" }}
            />
            {pasteText.length > 0 && pasteText.length < 200 && (
              <p style={{ fontSize: "var(--text-1)", color: "var(--danger)" }}>
                Please paste at least a few paragraphs for best results.
              </p>
            )}
          </div>
        )}

        {/* Focus prompt */}
        <div className="vstack" style={{ gap: "var(--space-2)" }}>
          <label htmlFor="focus_prompt" style={{ fontSize: "var(--text-2)", fontWeight: "var(--font-medium)" }}>
            What do you want to focus on?{" "}
            <span style={{ color: "var(--muted-foreground)", fontWeight: "var(--font-normal)" }}>(optional)</span>
          </label>
          <input
            id="focus_prompt"
            type="text"
            className="input-field"
            value={focusPrompt}
            onChange={(e) => setFocusPrompt(e.target.value)}
            placeholder="e.g. 'key algorithms', 'historical causes', 'main arguments'"
          />
        </div>

        <button
          type="submit"
          className="btn btn-primary"
          disabled={!selectedMode || isSubmitting || (pasteText.length > 0 && pasteText.length < 200)}
          style={{ alignSelf: "flex-start", fontSize: "var(--text-2)", padding: "var(--space-3) var(--space-6)" }}
        >
          {isSubmitting ? "Starting..." : "Generate my study session →"}
        </button>
      </form>

      <div style={{ marginTop: "var(--space-8)" }}>
        <Link href="/" className="btn btn-ghost" style={{ fontSize: "var(--text-1)" }}>
          ← Back
        </Link>
      </div>
    </main>
  );
}
