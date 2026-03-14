"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { TutoringType, SessionRequest } from "@/types/session";
import { useRecentSessions } from "@/app/hooks/useRecentSessions";

type InputMode = "url" | "topic" | "upload";

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
  const [generateFlashcards, setGenerateFlashcards] = useState(false);
  const [generateQuiz, setGenerateQuiz] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<{ error_kind: string; message: string } | null>(null);
  const [uploadProgressMessage, setUploadProgressMessage] = useState<string | null>(null);

  const { saveSession } = useRecentSessions();

  const MAX_FILE_BYTES = 20 * 1024 * 1024; // 20 MB

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setFileError(null);
    setUploadError(null);
    if (!file) { setSelectedFile(null); return; }
    if (file.size > MAX_FILE_BYTES) {
      setFileError("File is too large. Maximum file size is 20 MB.");
      setSelectedFile(null);
      e.target.value = ""; // reset so same file can be re-selected after correction
      return;
    }
    setSelectedFile(file);
  }

  const errorMessages = errorKind ? ERROR_MESSAGES[errorKind] ?? ERROR_MESSAGES.empty : null;

  async function handleUploadSubmit() {
    if (!selectedMode || !selectedFile) return;
    setIsSubmitting(true);
    setUploadError(null);
    setUploadProgressMessage("Uploading your file...");

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("tutoring_type", selectedMode);
    if (focusPrompt) formData.append("focus_prompt", focusPrompt);
    formData.append("generate_flashcards", String(generateFlashcards));
    formData.append("generate_quiz", String(generateQuiz));

    let res: Response;
    try {
      res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/sessions/upload`, {
        method: "POST",
        body: formData,
        // DO NOT set Content-Type — browser sets multipart/form-data with correct boundary automatically
      });
    } catch {
      setUploadError({ error_kind: "network_error", message: "Could not reach the server. Check your connection and try again." });
      setIsSubmitting(false);
      setUploadProgressMessage(null);
      return;
    }

    // Pre-stream HTTP errors (400 unsupported_format, 413 file_too_large, 422 scanned_pdf)
    if (!res.ok) {
      try {
        const errBody = await res.json();
        const detail = errBody.detail ?? {};
        setUploadError({
          error_kind: detail.error_kind ?? "upload_error",
          message: detail.message ?? "Upload failed. Please try again.",
        });
      } catch {
        setUploadError({ error_kind: "upload_error", message: "Upload failed. Please try again." });
      }
      setIsSubmitting(false);
      setUploadProgressMessage(null);
      return;
    }

    // SSE stream — session_id arrives in the 'complete' event
    if (!res.body) {
      setUploadError({ error_kind: "upload_error", message: "No response stream. Please try again." });
      setIsSubmitting(false);
      setUploadProgressMessage(null);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentEvent = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            const raw = line.slice(6).trim();
            if (!raw) continue;
            try {
              const parsed = JSON.parse(raw);
              if (currentEvent === "progress" && parsed.message) {
                setUploadProgressMessage(parsed.message);
              } else if (currentEvent === "complete" && parsed.session_id) {
                saveSession({
                  session_id: parsed.session_id,
                  source_title: selectedFile.name,
                  tutoring_type: selectedMode,
                  session_type: "upload",
                });
                router.push(`/study/${parsed.session_id}`);
                return;
              } else if (currentEvent === "error") {
                setUploadError({
                  error_kind: parsed.error_kind ?? "workflow_error",
                  message: parsed.message ?? "An error occurred during processing.",
                });
                setIsSubmitting(false);
                setUploadProgressMessage(null);
                return;
              }
            } catch {
              // Ignore non-JSON lines
            }
          }
        }
      }
    } catch {
      setUploadError({ error_kind: "workflow_error", message: "Connection lost during upload. Please try again." });
      setIsSubmitting(false);
      setUploadProgressMessage(null);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedMode) return;

    // Upload mode has its own SSE-based submission path
    if (inputMode === "upload") {
      await handleUploadSubmit();
      return;
    }

    setIsSubmitting(true);
    setErrorKind(null);

    const payload: SessionRequest = {
      tutoring_type: selectedMode,
      focus_prompt: focusPrompt || undefined,
      generate_flashcards: generateFlashcards || undefined,
      generate_quiz: generateQuiz || undefined,
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
      // Add to recent sessions immediately so the user can find it even if they navigate away
      const tempTitle = inputMode === "topic"
        ? topicDescription.trim().slice(0, 60)
        : pasteText ? "Pasted text" : (url || "Article");
      saveSession({
        session_id,
        source_title: tempTitle,
        tutoring_type: selectedMode,
        session_type: inputMode === "topic" ? "topic" : pasteText ? "paste" : "url",
      });
      router.push(
        `/loading?session_id=${session_id}&tutoring_type=${selectedMode}&focus_prompt=${encodeURIComponent(focusPrompt)}&input_mode=${inputMode}&generate_flashcards=${generateFlashcards}&generate_quiz=${generateQuiz}`
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
        <div className="flex rounded-lg border border-zinc-200 overflow-hidden w-full sm:w-auto">
          <button
            type="button"
            onClick={() => { setInputMode("url"); setTopicDescription(""); setUploadError(null); setUploadProgressMessage(null); }}
            className={`flex-1 sm:flex-none px-4 py-2 text-sm font-medium transition-colors ${
              inputMode === "url" ? "bg-zinc-900 text-white" : "bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            Article URL
          </button>
          <button
            type="button"
            onClick={() => { setInputMode("topic"); setUrl(""); setUploadError(null); setUploadProgressMessage(null); }}
            className={`flex-1 sm:flex-none px-4 py-2 text-sm font-medium transition-colors ${
              inputMode === "topic" ? "bg-zinc-900 text-white" : "bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            Topic description
          </button>
          <button
            type="button"
            onClick={() => { setInputMode("upload"); setUrl(""); setTopicDescription(""); setSelectedFile(null); setFileError(null); setUploadError(null); setUploadProgressMessage(null); }}
            className={`flex-1 sm:flex-none px-4 py-2 text-sm font-medium transition-colors ${
              inputMode === "upload" ? "bg-zinc-900 text-white" : "bg-white text-zinc-500 hover:bg-zinc-50"
            }`}
          >
            Upload file
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
            {topicDescription.length > 0 && topicDescription.length < 10 && (
              <p className="text-xs text-red-500">
                Please describe your topic in a bit more detail (at least a few words).
              </p>
            )}
            {topicDescription.length >= 10 && topicDescription.trim().split(/\s+/).length < 3 && (
              <p className="text-xs text-amber-600">
                Your topic is quite broad — consider adding more detail for better results.
              </p>
            )}
          </div>
        )}

        {/* File upload input — replaced by spinner while streaming */}
        {inputMode === "upload" && isSubmitting && (
          <div className="flex flex-col items-center gap-3 py-8">
            <span className="spinner" />
            <p className="text-sm text-zinc-600 text-center">
              {uploadProgressMessage ?? "Processing your file..."}
            </p>
          </div>
        )}

        {inputMode === "upload" && !isSubmitting && (
          <div className="flex flex-col gap-2">
            <label htmlFor="file_upload" className="text-sm font-medium text-zinc-900">
              Upload a PDF or Word document
            </label>
            <input
              id="file_upload"
              type="file"
              accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              onChange={handleFileChange}
              className="w-full text-sm text-zinc-700 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-medium file:bg-zinc-100 file:text-zinc-700 hover:file:bg-zinc-200 transition-colors cursor-pointer"
            />
            {fileError && (
              <p className="text-xs text-red-500" role="alert">{fileError}</p>
            )}
            {selectedFile && !fileError && (
              <p className="text-xs text-zinc-500">
                Selected: {selectedFile.name} ({(selectedFile.size / (1024 * 1024)).toFixed(1)} MB)
              </p>
            )}
          </div>
        )}

        {/* Upload error display — error_kind-aware messaging */}
        {inputMode === "upload" && uploadError && (
          <div className="flex flex-col gap-2 p-4 rounded-xl border border-red-200 bg-red-50" role="alert">
            <p className="font-semibold text-sm text-red-700">
              {uploadError.error_kind === "scanned_pdf"
                ? "This PDF can't be read"
                : uploadError.error_kind === "file_too_large"
                ? "File too large"
                : uploadError.error_kind === "unsupported_format"
                ? "Unsupported file type"
                : "Upload failed"}
            </p>
            <p className="text-xs text-red-600">
              {uploadError.error_kind === "scanned_pdf"
                ? "This PDF appears to be scanned or image-only — we can't extract text from it. Try a text-based PDF, or use the Topic tab to learn about the subject instead."
                : uploadError.message}
            </p>
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

        {/* Opt-in generation checkboxes */}
        <fieldset className="border-none p-0 m-0">
          <legend className="text-sm font-medium text-zinc-500 mb-3">
            Generate upfront <span className="text-zinc-400 font-normal">(optional — you can also generate later)</span>
          </legend>
          <div className="flex flex-col gap-2">
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={generateFlashcards}
                onChange={(e) => setGenerateFlashcards(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-zinc-700">Flashcards <span className="text-zinc-400">(8-12 cards)</span></span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={generateQuiz}
                onChange={(e) => setGenerateQuiz(e.target.checked)}
                className="w-4 h-4 rounded border-zinc-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-zinc-700">Quiz <span className="text-zinc-400">(8-10 questions)</span></span>
            </label>
          </div>
        </fieldset>

        <button
          type="submit"
          className="w-full sm:w-auto sm:self-start px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          disabled={
            !selectedMode ||
            isSubmitting ||
            (pasteText.length > 0 && pasteText.length < 200) ||
            (inputMode === "topic" && !pasteText && topicDescription.length < 10) ||
            (inputMode === "url" && !pasteText && !url.trim()) ||
            (inputMode === "upload" && !selectedFile)
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
