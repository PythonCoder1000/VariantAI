const SECTIONS = [
  { title: "Clinical Risk", icon: "⚠️" },
  { title: "Gene Function", icon: "🧬" },
  { title: "Structural Impact", icon: "🔬" },
  { title: "Research Summary", icon: "📚" },
  { title: "Bottom Line", icon: "💡", highlight: true },
];

function SkeletonLine({ width, delay }: { width: string; delay: number }) {
  return (
    <div
      className="h-3 animate-pulse rounded bg-gray-800"
      style={{ width, animationDelay: `${delay}ms` }}
    />
  );
}

export default function SkeletonReport() {
  return (
    <div className="mt-8 space-y-4" aria-hidden="true">
      {/* Header skeleton */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="h-8 w-32 animate-pulse rounded-md bg-gray-800" />
          <div className="h-4 w-48 animate-pulse rounded bg-gray-800/60" />
        </div>
        <div className="h-6 w-28 animate-pulse rounded-full bg-gray-800" />
      </div>

      {/* Section skeletons */}
      {SECTIONS.map(({ title, icon, highlight }, i) => (
        <div
          key={title}
          className={`p-5 rounded-lg border ${
            highlight ? "bg-blue-950 border-blue-800" : "bg-gray-900 border-gray-700"
          }`}
        >
          <div className="mb-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {icon && <span className="mr-1.5">{icon}</span>}
            {title}
          </div>
          <div className="space-y-2">
            <SkeletonLine width="100%" delay={i * 60} />
            <SkeletonLine width="88%" delay={i * 60 + 30} />
            <SkeletonLine width="67%" delay={i * 60 + 60} />
          </div>
        </div>
      ))}
    </div>
  );
}
