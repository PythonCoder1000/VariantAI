"use client";

import { useEffect, useState } from "react";
import type { MemoryItem } from "@/lib/types";

interface Props {
  onClose: () => void;
}

const apiUrl = () => process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Render this component only while the modal is open (mount-fresh each time):
 * its data fetch then runs once on mount with every setState after an `await`,
 * which keeps the React 19 "no synchronous setState in effects" rule happy and
 * guarantees fresh memory on each open.
 */
export default function MemoryModal({ onClose }: Props) {
  const [items, setItems] = useState<MemoryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch on mount.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const resp = await fetch(`${apiUrl()}/api/memory`);
        if (cancelled) return;
        if (!resp.ok) throw new Error(`Server error ${resp.status}`);
        const data = await resp.json();
        if (cancelled) return;
        setItems(data.items ?? []);
      } catch {
        if (!cancelled) setError("Could not load memory. Is the backend running?");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const clearAll = async () => {
    try {
      await fetch(`${apiUrl()}/api/memory`, { method: "DELETE" });
      setItems([]);
    } catch {
      setError("Could not clear memory.");
    }
  };

  const loading = items === null && error === null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="animate-fade-in-up w-full max-w-lg rounded-xl border border-gray-800 bg-gray-900 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-5 py-4">
          <div>
            <h2 className="text-base font-semibold text-gray-100">Memory</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              Facts the assistant remembers across all your chats.
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-gray-500 transition-colors hover:bg-gray-800 hover:text-gray-200"
          >
            <svg viewBox="0 0 20 20" className="h-5 w-5" fill="currentColor">
              <path d="M6.3 5.3a1 1 0 0 0-1.4 1.4L8.6 10l-3.7 3.3a1 1 0 1 0 1.4 1.4L10 11.4l3.3 3.3a1 1 0 0 0 1.4-1.4L11.4 10l3.3-3.3a1 1 0 0 0-1.4-1.4L10 8.6 6.3 5.3Z" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="max-h-[55vh] overflow-y-auto px-5 py-4">
          {loading ? (
            <p className="text-sm text-gray-500">Loading…</p>
          ) : error ? (
            <p className="text-sm text-red-400">{error}</p>
          ) : items && items.length === 0 ? (
            <div className="py-6 text-center">
              <p className="mb-1 text-3xl">🧠</p>
              <p className="text-sm text-gray-400">No memories saved yet.</p>
              <p className="mt-1 text-xs text-gray-600">
                Tell the assistant something durable (e.g. &ldquo;I&apos;m a clinician&rdquo;) and
                it&apos;ll remember.
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {items?.map((item) => (
                <li
                  key={item.id}
                  className="flex items-start gap-2.5 rounded-lg border border-gray-800 bg-gray-950/50 px-3 py-2.5"
                >
                  <span className="mt-0.5 text-blue-400">•</span>
                  <span className="text-sm text-gray-200">{item.text}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Footer */}
        {items && items.length > 0 && (
          <div className="flex justify-end border-t border-gray-800 px-5 py-3">
            <button
              onClick={clearAll}
              className="rounded-lg border border-red-900 px-3 py-1.5 text-xs font-medium text-red-400
                         transition-colors hover:bg-red-950"
            >
              Clear all memory
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
