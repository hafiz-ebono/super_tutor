"use client";
import { useState, useEffect, useCallback, useRef } from "react";

const STORAGE_KEY = "super_tutor_recent_sessions";
const MAX_SESSIONS = 5;

export interface StoredSession {
  session_id: string;
  source_title: string;
  tutoring_type: string;
  session_type: string;
  saved_at: string;
}

function readFromStorage(): StoredSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function writeToStorage(sessions: StoredSession[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // Silently handle quota errors
  }
}

export function useRecentSessions() {
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [evictionToast, setEvictionToast] = useState(false);
  const evictionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setSessions(readFromStorage());
    return () => {
      if (evictionTimerRef.current) clearTimeout(evictionTimerRef.current);
    };
  }, []);

  const saveSession = useCallback((entry: Omit<StoredSession, "saved_at">) => {
    const current = readFromStorage();
    // Remove duplicate (same session_id) if already saved
    const deduplicated = current.filter((s) => s.session_id !== entry.session_id);
    const newEntry: StoredSession = { ...entry, saved_at: new Date().toISOString() };
    const next = [newEntry, ...deduplicated];

    let evicted = false;
    let trimmed = next;
    if (next.length > MAX_SESSIONS) {
      trimmed = next.slice(0, MAX_SESSIONS);
      evicted = true;
    }

    writeToStorage(trimmed);
    setSessions(trimmed);

    if (evicted) {
      setEvictionToast(true);
      if (evictionTimerRef.current) clearTimeout(evictionTimerRef.current);
      evictionTimerRef.current = setTimeout(() => setEvictionToast(false), 3000);
    }
  }, []);

  const removeSession = useCallback((session_id: string) => {
    const updated = readFromStorage().filter((s) => s.session_id !== session_id);
    writeToStorage(updated);
    setSessions(updated);
    // Clean up cached session detail and chat history
    try {
      localStorage.removeItem(`session:${session_id}`);
      localStorage.removeItem(`chat:${session_id}`);
    } catch {
      // Ignore storage errors
    }
  }, []);

  return { sessions, saveSession, removeSession, evictionToast };
}
