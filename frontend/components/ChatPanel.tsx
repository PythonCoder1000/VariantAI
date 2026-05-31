"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import type { ChatMessage } from "@/lib/types";

interface Props {
  variantId: string;
  messages: ChatMessage[];
  busy: boolean;
  onSend: (text: string) => void;
}

const SUGGESTIONS = [
  "Should I be worried about this?",
  "Explain the gene function in simple terms",
  "What does this mean for my family?",
  "How was this variant studied?",
];

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`animate-fade-in-up max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser
            ? "rounded-br-sm bg-blue-600 text-white"
            : "rounded-bl-sm bg-gray-800 text-gray-100"
        }`}
      >
        {message.content}
        {message.pending && (
          <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-gray-400 align-text-bottom" />
        )}
      </div>
    </div>
  );
}

export default function ChatPanel({ variantId, messages, busy, onSend }: Props) {
  const [draft, setDraft] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    onSend(text);
  };

  return (
    <div className="mt-8 rounded-xl border border-gray-800 bg-gray-900/40">
      <div className="border-b border-gray-800 px-5 py-3">
        <h3 className="text-sm font-semibold text-gray-200">
          Ask a follow-up
          <span className="ml-2 font-mono text-xs font-normal text-gray-500">{variantId}</span>
        </h3>
      </div>

      {/* Messages */}
      <div className="max-h-[28rem] space-y-3 overflow-y-auto px-5 py-4">
        {messages.length === 0 ? (
          <div className="py-2">
            <p className="mb-3 text-sm text-gray-500">
              Ask anything about this variant — its risk, the gene, the research, or what it
              means for you.
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => !busy && onSend(s)}
                  disabled={busy}
                  className="rounded-full border border-gray-700 px-3 py-1.5 text-xs text-gray-300
                             transition-colors hover:border-gray-500 hover:bg-gray-800 disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m, i) => <MessageBubble key={i} message={m} />)
        )}
        <div ref={endRef} />
      </div>

      {/* Input */}
      <form onSubmit={submit} className="border-t border-gray-800 p-3">
        <div className="flex gap-2">
          <input
            type="text"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type your question…"
            disabled={busy}
            className="flex-1 rounded-lg border border-gray-700 bg-gray-900 px-4 py-2.5 text-sm
                       text-gray-100 placeholder-gray-600 focus:border-transparent
                       focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
            aria-label="Follow-up question"
          />
          <button
            type="submit"
            disabled={busy || !draft.trim()}
            className="flex items-center justify-center rounded-lg bg-blue-600 px-4 py-2.5 text-white
                       transition-all hover:bg-blue-500 active:scale-95 disabled:opacity-40
                       disabled:cursor-not-allowed"
            aria-label="Send"
          >
            {busy ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            ) : (
              <svg viewBox="0 0 20 20" className="h-4 w-4" fill="currentColor">
                <path d="M3.4 2.6a1 1 0 0 0-1.3 1.2l1.8 5.4a1 1 0 0 0 .8.67l8.3 1.13-8.3 1.13a1 1 0 0 0-.8.67l-1.8 5.4a1 1 0 0 0 1.3 1.2l14-7a1 1 0 0 0 0-1.8l-14-7Z" />
              </svg>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
