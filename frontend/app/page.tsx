"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import VariantInput from "@/components/VariantInput";
import AnalysisProgress from "@/components/AnalysisProgress";
import ReportCard from "@/components/ReportCard";
import SkeletonReport from "@/components/SkeletonReport";
import ChatPanel from "@/components/ChatPanel";
import Sidebar from "@/components/Sidebar";
import MemoryModal from "@/components/MemoryModal";
import { loadSessions, saveSessions, newSessionId } from "@/lib/storage";
import type { ChatSession, VariantReport } from "@/lib/types";

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Read an SSE response body, invoking onEvent(type, data) per message. */
async function readSSE(
  body: ReadableStream<Uint8Array>,
  onEvent: (type: string, data: Record<string, unknown>) => void
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const messages = buffer.split("\n\n");
    buffer = messages.pop() ?? "";
    for (const msg of messages) {
      const eventMatch = msg.match(/^event:\s*(\w+)/m);
      const dataMatch = msg.match(/^data:\s*(.+)$/m);
      if (!eventMatch || !dataMatch) continue;
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(dataMatch[1]);
      } catch {
        continue;
      }
      onEvent(eventMatch[1], data);
    }
  }
}

export default function Home() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [chatBusy, setChatBusy] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  // Load persisted sessions once on mount.
  useEffect(() => {
    setSessions(loadSessions());
    setMounted(true);
  }, []);

  // Persist on change (skip the pre-mount empty state so we don't clobber storage).
  useEffect(() => {
    if (mounted) saveSessions(sessions);
  }, [sessions, mounted]);

  // Auto-dismiss the memory toast.
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeId) ?? null,
    [sessions, activeId]
  );

  const updateSession = useCallback(
    (id: string, updater: (s: ChatSession) => ChatSession) => {
      setSessions((prev) =>
        prev.map((s) => (s.id === id ? { ...updater(s), updatedAt: Date.now() } : s))
      );
    },
    []
  );

  // ── Analyze a new variant ──────────────────────────────────────────────────
  const handleAnalyze = useCallback(
    async (rsId: string) => {
      const id = newSessionId();
      const now = Date.now();
      const session: ChatSession = {
        id,
        variantId: rsId,
        status: "analyzing",
        report: null,
        error: null,
        messages: [],
        createdAt: now,
        updatedAt: now,
      };
      setSessions((prev) => [session, ...prev]);
      setActiveId(id);
      setProgressLog([]);
      setSidebarOpen(false);

      let response: Response;
      try {
        response = await fetch(`${apiUrl()}/api/analyze`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ variant_id: rsId }),
        });
      } catch {
        updateSession(id, (s) => ({
          ...s,
          status: "error",
          error: "Could not reach the analysis server. Is the backend running?",
        }));
        return;
      }

      if (!response.ok || !response.body) {
        const msg =
          response.status === 429
            ? "Rate limit reached (5 analyses/min). Please wait a moment and try again."
            : `Server error: ${response.status} ${response.statusText}`;
        updateSession(id, (s) => ({ ...s, status: "error", error: msg }));
        return;
      }

      try {
        await readSSE(response.body, (type, data) => {
          if (type === "progress") {
            setProgressLog((prev) => [...prev, (data.text as string) ?? ""]);
          } else if (type === "complete") {
            if (data.report) {
              updateSession(id, (s) => ({
                ...s,
                status: "complete",
                report: data.report as VariantReport,
              }));
            } else {
              updateSession(id, (s) => ({
                ...s,
                status: "error",
                error:
                  (data.error as string) ?? "Analysis finished but the report could not be parsed.",
              }));
            }
          } else if (type === "not_found") {
            updateSession(id, (s) => ({ ...s, status: "unknown" }));
          } else if (type === "error") {
            updateSession(id, (s) => ({
              ...s,
              status: "error",
              error: (data.error as string) ?? "Unknown error from server.",
            }));
          }
        });
      } catch (err) {
        updateSession(id, (s) => ({ ...s, status: "error", error: `Stream read error: ${String(err)}` }));
      }
    },
    [updateSession]
  );

  // ── Send a follow-up chat message ────────────────────────────────────────
  const handleSend = useCallback(
    async (text: string) => {
      if (!activeSession || chatBusy) return;
      const id = activeSession.id;
      const history = [...activeSession.messages, { role: "user" as const, content: text }];

      // Optimistically render the user message + a pending assistant bubble.
      updateSession(id, (s) => ({
        ...s,
        messages: [
          ...s.messages,
          { role: "user", content: text },
          { role: "assistant", content: "", pending: true },
        ],
      }));
      setChatBusy(true);

      const setAssistant = (content: string, pending: boolean) =>
        updateSession(id, (s) => {
          const msgs = [...s.messages];
          for (let i = msgs.length - 1; i >= 0; i--) {
            if (msgs[i].role === "assistant") {
              msgs[i] = { role: "assistant", content, pending };
              break;
            }
          }
          return { ...s, messages: msgs };
        });

      let response: Response;
      try {
        response = await fetch(`${apiUrl()}/api/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            variant_id: activeSession.variantId,
            report: activeSession.report,
            messages: history,
          }),
        });
      } catch {
        setAssistant("⚠️ Could not reach the server. Is the backend running?", false);
        setChatBusy(false);
        return;
      }

      if (!response.ok || !response.body) {
        const msg =
          response.status === 429
            ? "⚠️ Rate limit reached (20 messages/min). Please wait a moment."
            : `⚠️ Server error: ${response.status} ${response.statusText}`;
        setAssistant(msg, false);
        setChatBusy(false);
        return;
      }

      let streamed = "";
      try {
        await readSSE(response.body, (type, data) => {
          if (type === "delta") {
            streamed += (data.text as string) ?? "";
            setAssistant(streamed, true);
          } else if (type === "done") {
            setAssistant((data.text as string) ?? streamed, false);
            const added = (data.memories_added as string[]) ?? [];
            if (added.length > 0) {
              setToast(`Saved to memory: ${added.join("; ")}`);
            }
          } else if (type === "error") {
            setAssistant(`⚠️ ${(data.error as string) ?? "Something went wrong."}`, false);
          }
        });
      } catch (err) {
        setAssistant(`⚠️ Stream error: ${String(err)}`, false);
      }
      setChatBusy(false);
    },
    [activeSession, chatBusy, updateSession]
  );

  // ── Sidebar actions ────────────────────────────────────────────────────────
  const handleNew = useCallback(() => {
    setActiveId(null);
    setProgressLog([]);
    setSidebarOpen(false);
  }, []);

  const handleSelect = useCallback((id: string) => {
    setActiveId(id);
    setSidebarOpen(false);
  }, []);

  const handleDelete = useCallback(
    (id: string) => {
      setSessions((prev) => prev.filter((s) => s.id !== id));
      setActiveId((cur) => (cur === id ? null : cur));
    },
    []
  );

  return (
    <div className="flex h-screen overflow-hidden bg-gray-950 text-gray-100">
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-40 w-72 transform transition-transform duration-200 md:static md:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <Sidebar
          sessions={sessions}
          activeId={activeId}
          onSelect={handleSelect}
          onNew={handleNew}
          onDelete={handleDelete}
          onOpenMemory={() => setMemoryOpen(true)}
        />
      </div>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        {/* Mobile top bar */}
        <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-gray-800 bg-gray-950/90 px-4 py-3 backdrop-blur md:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open menu"
            className="rounded-lg p-1.5 text-gray-300 hover:bg-gray-800"
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="currentColor">
              <path d="M3 5.5A1 1 0 0 1 4 4.5h12a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1Zm0 4.5a1 1 0 0 1 1-1h12a1 1 0 1 1 0 2H4a1 1 0 0 1-1-1Zm1 3.5a1 1 0 1 0 0 2h12a1 1 0 1 0 0-2H4Z" />
            </svg>
          </button>
          <span className="font-semibold">VariantAI</span>
        </div>

        <div className="mx-auto max-w-3xl px-4 py-10 md:py-16">
          {/* Landing / new analysis */}
          {!activeSession && (
            <>
              <div className="mb-12 text-center">
                <h1 className="mb-3 text-4xl font-bold text-gray-100">VariantAI</h1>
                <p className="text-lg text-gray-500">
                  Enter a genomic rsID to receive a plain-language clinical analysis.
                </p>
              </div>
              <VariantInput onAnalyze={handleAnalyze} disabled={false} />
            </>
          )}

          {/* Active session view */}
          {activeSession && (
            <>
              {activeSession.status === "analyzing" && (
                <>
                  <AnalysisProgress log={progressLog} />
                  <SkeletonReport />
                </>
              )}

              {activeSession.status === "complete" && activeSession.report && (
                <>
                  <ReportCard report={activeSession.report} />
                  <ChatPanel
                    variantId={activeSession.variantId}
                    messages={activeSession.messages}
                    busy={chatBusy}
                    onSend={handleSend}
                  />
                </>
              )}

              {activeSession.status === "unknown" && (
                <div className="rounded-lg border border-gray-700 bg-gray-900 p-6 text-center">
                  <p className="mb-3 text-3xl">🔍</p>
                  <h3 className="mb-2 text-lg font-semibold text-gray-200">Unknown Variant</h3>
                  <p className="text-sm text-gray-400">
                    <strong className="font-mono text-gray-300">{activeSession.variantId}</strong>{" "}
                    was not found in any genomic database. Please verify the rsID and try again.
                  </p>
                  <button
                    onClick={handleNew}
                    className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
                  >
                    New analysis
                  </button>
                </div>
              )}

              {activeSession.status === "error" && (
                <div className="rounded-lg border border-red-800 bg-red-950/50 p-4">
                  <p className="text-red-400">
                    <strong>Error:</strong> {activeSession.error}
                  </p>
                  <button
                    onClick={handleNew}
                    className="mt-3 rounded-lg border border-gray-700 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-800"
                  >
                    Start a new analysis
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {/* Memory modal (mounted only while open so it fetches fresh each time) */}
      {memoryOpen && <MemoryModal onClose={() => setMemoryOpen(false)} />}

      {/* Toast */}
      {toast && (
        <div className="animate-fade-in-up fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm text-gray-200 shadow-xl">
          🧠 {toast}
        </div>
      )}
    </div>
  );
}
