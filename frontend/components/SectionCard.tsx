interface Props {
  title: string;
  content: string;
  icon?: string;
  highlight?: boolean;
  index?: number;
}

export default function SectionCard({ title, content, icon, highlight = false, index = 0 }: Props) {
  return (
    <div
      className={`animate-fade-in-up p-5 rounded-lg border shadow-sm transition-colors hover:border-gray-600 ${
        highlight
          ? "bg-blue-950 border-blue-800 hover:border-blue-700"
          : "bg-gray-900 border-gray-700"
      }`}
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
        {icon && <span className="mr-1.5">{icon}</span>}
        {title}
      </h3>
      <p className="text-gray-200 leading-relaxed text-sm">
        {content || <span className="italic text-gray-600">No data available</span>}
      </p>
    </div>
  );
}
