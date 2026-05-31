"use client";

import type { ChatSession, SessionStatus } from "@/lib/types";

interface Props {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onOpenMemory: () => void;
}

const STATUS_DOT: Record<SessionStatus, string> = {
  analyzing: "bg-blue-400 animate-pulse",
  complete: "bg-emerald-400",
  error: "bg-red-400",
  unknown: "bg-gray-500",
};

function relativeTime(ts: number): string {
  const diff = Date.now() - ts;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onOpenMemory,
}: Props) {
  return (
    <aside className="flex h-full w-full flex-col bg-gray-900/60 border-r border-gray-800">
      {/* Brand */}
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="text-xl">🧬</span>
        <span className="text-lg font-bold text-gray-100">VariantAI</span>
      </div>

      {/* New analysis */}
      <div className="px-3">
        <button
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-gray-700
                     bg-blue-600 px-3 py-2.5 text-sm font-medium text-white
                     transition-colors hover:bg-blue-500"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
            <path d="M10 4a1 1 0 0 1 1 1v4h4a1 1 0 1 1 0 2h-4v4a1 1 0 1 1-2 0v-4H5a1 1 0 1 1 0-2h4V5a1 1 0 0 1 1-1Z" />
          </svg>
          New analysis
        </button>
      </div>

      {/* Session list */}
      <div className="mt-4 flex-1 overflow-y-auto px-2">
        <p className="px-2 pb-2 text-xs font-semibold uppercase tracking-wide text-gray-600">
          History
        </p>
        {sessions.length === 0 ? (
          <p className="px-2 text-sm text-gray-600">No analyses yet.</p>
        ) : (
          <ul className="space-y-1">
            {sessions.map((s) => {
              const active = s.id === activeId;
              return (
                <li key={s.id}>
                  <div
                    className={`group flex items-center gap-2 rounded-lg px-2 py-2 transition-colors ${
                      active ? "bg-gray-800" : "hover:bg-gray-800/60"
                    }`}
                  >
                    <button
                      onClick={() => onSelect(s.id)}
                      className="flex min-w-0 flex-1 items-center gap-2.5 text-left"
                    >
                      <span
                        className={`h-2 w-2 flex-shrink-0 rounded-full ${STATUS_DOT[s.status]}`}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-mono text-sm text-gray-200">
                          {s.variantId}
                        </span>
                        <span className="block text-xs text-gray-600">
                          {s.messages.length > 0
                            ? `${s.messages.length} message${s.messages.length === 1 ? "" : "s"} · ${relativeTime(s.updatedAt)}`
                            : relativeTime(s.updatedAt)}
                        </span>
                      </span>
                    </button>
                    <button
                      onClick={() => onDelete(s.id)}
                      aria-label={`Delete ${s.variantId} analysis`}
                      className="flex-shrink-0 rounded p-1 text-gray-600 opacity-0 transition
                                 hover:text-red-400 group-hover:opacity-100"
                    >
                      <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                        <path
                          fillRule="evenodd"
                          d="M8.75 1.75a.75.75 0 0 0-.75.75v.5H4.5a.75.75 0 0 0 0 1.5h.3l.6 11.1A2 2 0 0 0 7.7 18.5h4.6a2 2 0 0 0 2-1.9l.6-11.1h.3a.75.75 0 0 0 0-1.5H12v-.5a.75.75 0 0 0-.75-.75h-2.5ZM8.5 7a.75.75 0 0 1 .75.75v6a.75.75 0 0 1-1.5 0v-6A.75.75 0 0 1 8.5 7Zm3.75.75a.75.75 0 0 0-1.5 0v6a.75.75 0 0 0 1.5 0v-6Z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Memory */}
      <div className="border-t border-gray-800 p-3">
        <button
          onClick={onOpenMemory}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-gray-400
                     transition-colors hover:bg-gray-800 hover:text-gray-200"
        >
          <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
            <path d="M10 2a5 5 0 0 0-5 5c0 1.4.57 2.67 1.5 3.58V13a1 1 0 0 0 1 1h5a1 1 0 0 0 1-1v-2.42A5 5 0 0 0 10 2ZM7.5 16a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1 1 1 0 0 1-1 1h-3a1 1 0 0 1-1-1Z" />
          </svg>
          Memory
        </button>
      </div>
    </aside>
  );
}
