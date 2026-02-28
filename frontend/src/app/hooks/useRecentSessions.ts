"use client";
import { useState, useEffect, useCallback } from "react";

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

  useEffect(() => {
    setSessions(readFromStorage());
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
      setTimeout(() => setEvictionToast(false), 3000);
    }
  }, []);

  return { sessions, saveSession, evictionToast };
}
