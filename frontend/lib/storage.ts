import type { ChatSession } from "./types";

const STORAGE_KEY = "variantai.sessions.v1";

/** Load all saved sessions, newest first. Returns [] on the server or if absent. */
export function loadSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as ChatSession[];
    if (!Array.isArray(parsed)) return [];
    // A session left mid-analysis (e.g. a reload during streaming) can't resume —
    // surface it as an error rather than a perpetual spinner.
    const normalized = parsed.map((s) =>
      s.status === "analyzing"
        ? { ...s, status: "error" as const, error: "Analysis was interrupted. Please run it again." }
        : s
    );
    return normalized.sort((a, b) => b.updatedAt - a.updatedAt);
  } catch {
    return [];
  }
}

/** Persist the full session list. */
export function saveSessions(sessions: ChatSession[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    // Quota exceeded or storage disabled — fail silently; in-memory state still works.
  }
}

export function newSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `s_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
}
