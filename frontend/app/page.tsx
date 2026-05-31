"use client";

import { useState } from "react";
import VariantInput from "@/components/VariantInput";
import AnalysisProgress from "@/components/AnalysisProgress";
import ReportCard from "@/components/ReportCard";

interface VariantReport {
  variant_id: string;
  gene?: string;
  variant_type?: string;
  clinical_risk: string;
  gene_function: string;
  structural_impact: string;
  research_summary: string;
  bottom_line: string;
  confidence: string;
  sources: Array<{ db: string; [key: string]: unknown }>;
}

type Status = "idle" | "analyzing" | "complete" | "error";

export default function Home() {
  const [status, setStatus] = useState<Status>("idle");
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [report, setReport] = useState<VariantReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (rsId: string) => {
    setStatus("analyzing");
    setProgressLog([]);
    setReport(null);
    setError(null);

    const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    let response: Response;
    try {
      response = await fetch(`${apiUrl}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_id: rsId }),
      });
    } catch {
      setError("Could not reach the analysis server. Is the backend running?");
      setStatus("error");
      return;
    }

    if (!response.ok || !response.body) {
      setError(`Server error: ${response.status} ${response.statusText}`);
      setStatus("error");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
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

          const eventType = eventMatch[1];
          const data = JSON.parse(dataMatch[1]);

          if (eventType === "progress") {
            setProgressLog((prev) => [...prev, data.text ?? ""]);
          } else if (eventType === "complete") {
            if (data.report) {
              setReport(data.report as VariantReport);
              setStatus("complete");
            } else {
              setError(data.error ?? "Analysis finished but report could not be parsed.");
              setStatus("error");
            }
          } else if (eventType === "error") {
            setError(data.error ?? "Unknown error from server.");
            setStatus("error");
          }
        }
      }
    } catch (err) {
      setError(`Stream read error: ${String(err)}`);
      setStatus("error");
    }
  };

  return (
    <main className="min-h-screen bg-gray-950">
      <div className="max-w-3xl mx-auto px-4 py-16">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-100 mb-3">VariantAI</h1>
          <p className="text-lg text-gray-500">
            Enter a genomic rsID to receive a plain-language clinical analysis.
          </p>
        </div>

        {/* Input */}
        <VariantInput onAnalyze={handleAnalyze} disabled={status === "analyzing"} />

        {/* Progress */}
        {status === "analyzing" && (
          <AnalysisProgress log={progressLog} />
        )}

        {/* Report */}
        {status === "complete" && report && (
          <ReportCard report={report} />
        )}

        {/* Error */}
        {status === "error" && error && (
          <div className="mt-8 p-4 bg-red-950/50 border border-red-800 rounded-lg">
            <p className="text-red-400"><strong>Error:</strong> {error}</p>
          </div>
        )}
      </div>
    </main>
  );
}
