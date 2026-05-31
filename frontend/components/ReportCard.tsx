"use client";

import { useState } from "react";
import SectionCard from "./SectionCard";
import SourceBadge from "./SourceBadge";

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

interface Props {
  report: VariantReport;
}

const CONFIDENCE_BADGE: Record<string, string> = {
  high:   "bg-emerald-950 text-emerald-400 border-emerald-800",
  medium: "bg-amber-950 text-amber-400 border-amber-800",
  low:    "bg-red-950 text-red-400 border-red-800",
};

function buildPlainText(report: VariantReport): string {
  return [
    `VariantAI Report: ${report.variant_id.toUpperCase()}`,
    report.gene
      ? `Gene: ${report.gene}${report.variant_type ? ` · ${report.variant_type}` : ""}`
      : "",
    `Confidence: ${report.confidence}`,
    "",
    `CLINICAL RISK\n${report.clinical_risk}`,
    "",
    `GENE FUNCTION\n${report.gene_function}`,
    "",
    `STRUCTURAL IMPACT\n${report.structural_impact}`,
    "",
    `RESEARCH SUMMARY\n${report.research_summary}`,
    "",
    `BOTTOM LINE\n${report.bottom_line}`,
  ]
    .filter((line) => line !== undefined)
    .join("\n");
}

export default function ReportCard({ report }: Props) {
  const [copied, setCopied] = useState(false);
  const badgeClass = CONFIDENCE_BADGE[report.confidence] ?? CONFIDENCE_BADGE.medium;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildPlainText(report));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard denied — silently ignore
    }
  };

  return (
    <div className="mt-8 space-y-4">
      {/* Header */}
      <div className="animate-fade-in-up flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-100 uppercase">
            {report.variant_id}
          </h2>
          {report.gene && (
            <p className="text-sm text-gray-500 mt-1">
              Gene: <strong className="text-gray-300">{report.gene}</strong>
              {report.variant_type && <> &middot; {report.variant_type}</>}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <button
            onClick={handleCopy}
            className="px-3 py-1 rounded-lg text-xs font-medium border border-gray-700
                       text-gray-400 hover:text-gray-200 hover:border-gray-500
                       transition-colors duration-150 whitespace-nowrap"
            aria-label="Copy report as plain text"
          >
            {copied ? "Copied!" : "Copy as text"}
          </button>
          <span className={`px-3 py-1 rounded-full text-xs font-semibold border ${badgeClass} whitespace-nowrap`}>
            {report.confidence} confidence
          </span>
        </div>
      </div>

      {/* Report Sections */}
      <SectionCard title="Clinical Risk"     content={report.clinical_risk}     icon="⚠️" index={0} />
      <SectionCard title="Gene Function"     content={report.gene_function}     icon="🧬" index={1} />
      <SectionCard title="Structural Impact" content={report.structural_impact} icon="🔬" index={2} />
      <SectionCard title="Research Summary"  content={report.research_summary}  icon="📚" index={3} />
      <SectionCard title="Bottom Line"       content={report.bottom_line}       icon="💡" highlight index={4} />

      {/* Sources */}
      {report.sources.length > 0 && (
        <div className="pt-4 border-t border-gray-800">
          <h3 className="text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">
            Sources
          </h3>
          <div className="flex flex-wrap gap-2">
            {report.sources.map((s, i) => (
              <SourceBadge key={i} source={s} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
