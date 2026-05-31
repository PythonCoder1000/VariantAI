"use client";

// Keys match strings that only appear when each skill *executes* (file paths in
// the skill code / stdout), not during the agent's opening step description.
const STAGES = [
  { key: "clinvar.json",    label: "Querying ClinVar" },
  { key: "dbsnp.json",      label: "Querying dbSNP" },
  { key: "gnomad.json",     label: "Querying gnomAD" },
  { key: "gene.json",       label: "Fetching gene info (NCBI Gene)" },
  { key: "uniprot.json",    label: "Fetching protein data (UniProt)" },
  { key: "pubmed.json",     label: "Searching PubMed" },
  { key: "ensembl.json",    label: "Running Ensembl VEP predictions" },
  { key: "raw data loaded", label: "Synthesizing report" },
];

const PREVIEW_CHARS = 500;

interface Props {
  log: string[];
}

function Dots() {
  return (
    <span className="inline-flex gap-[3px]" aria-hidden>
      <span className="animate-dot h-1 w-1 rounded-full bg-blue-400" style={{ animationDelay: "0ms" }} />
      <span className="animate-dot h-1 w-1 rounded-full bg-blue-400" style={{ animationDelay: "150ms" }} />
      <span className="animate-dot h-1 w-1 rounded-full bg-blue-400" style={{ animationDelay: "300ms" }} />
    </span>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 12 12" className="h-2.5 w-2.5 text-gray-950" fill="none" stroke="currentColor" strokeWidth={2.5}>
      <path d="M2.5 6.5L5 9l4.5-5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function AnalysisProgress({ log }: Props) {
  const fullLog = log.join(" ").toLowerCase();

  // Index of the last stage whose execution-specific key has appeared.
  const rawIndex = STAGES.reduce(
    (max, { key }, i) => (fullLog.includes(key) ? i : max),
    -1
  );
  // The component only renders while analyzing, so before any keyword arrives
  // the first stage is the one currently running (fixes "first item never runs").
  const activeIndex = Math.max(rawIndex, 0);

  // Live synthesis stream: everything after the "raw data loaded" marker.
  const synthBoundary = log.findIndex((msg) =>
    msg.toLowerCase().includes("raw data loaded")
  );
  const synthText = synthBoundary >= 0 ? log.slice(synthBoundary).join("") : "";
  const synthPreview =
    synthText.length > PREVIEW_CHARS ? synthText.slice(-PREVIEW_CHARS) : synthText;

  const pct = Math.min(100, ((activeIndex + 0.5) / STAGES.length) * 100);

  return (
    <div className="animate-fade-in-up mt-8 rounded-xl border border-gray-700 bg-gray-900 p-6 shadow-lg shadow-black/20">
      <h2 className="mb-5 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Analysis in Progress
      </h2>

      <ul className="space-y-1">
        {STAGES.map(({ key, label }, i) => {
          const done = i < activeIndex;
          const active = i === activeIndex;
          const isSynthesis = i === STAGES.length - 1;

          return (
            <li
              key={key}
              className={`relative overflow-hidden rounded-lg px-2.5 py-2 transition-colors duration-300 ${
                active ? "bg-blue-500/10" : ""
              }`}
            >
              {/* Shimmer sweep on the active row */}
              {active && (
                <span className="animate-shimmer pointer-events-none absolute inset-0 bg-gradient-to-r from-transparent via-blue-400/10 to-transparent" />
              )}

              <div className="relative flex items-center gap-3 text-sm">
                {/* Status indicator */}
                <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center">
                  {done ? (
                    <span className="animate-pop-in flex h-4 w-4 items-center justify-center rounded-full bg-emerald-400">
                      <CheckIcon />
                    </span>
                  ) : active ? (
                    <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-400/30 border-t-blue-400" />
                  ) : (
                    <span className="h-2.5 w-2.5 rounded-full bg-gray-700" />
                  )}
                </span>

                <span
                  className={`transition-colors duration-300 ${
                    done
                      ? "text-gray-500"
                      : active
                        ? "font-medium text-gray-100"
                        : "text-gray-600"
                  }`}
                >
                  {label}
                </span>

                {active && (
                  <span className="ml-auto flex items-center gap-1.5 text-xs text-blue-400">
                    <span>Running</span>
                    <Dots />
                  </span>
                )}
              </div>

              {/* Live synthesis preview */}
              {active && isSynthesis && synthPreview && (
                <div className="animate-fade-in-up relative ml-7 mt-2.5 max-h-28 overflow-hidden rounded-md border border-gray-700 bg-gray-950 px-3 py-2">
                  <div className="pointer-events-none absolute inset-x-0 top-0 h-8 bg-gradient-to-b from-gray-950 to-transparent" />
                  <p className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed text-gray-400">
                    {synthPreview}
                    <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-blue-400 align-text-bottom" />
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      {/* Animated progress bar */}
      <div className="mt-5 h-1.5 w-full overflow-hidden rounded-full bg-gray-800">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-400 transition-[width] duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-gray-600">
        Step {activeIndex + 1} of {STAGES.length}
      </p>
    </div>
  );
}
