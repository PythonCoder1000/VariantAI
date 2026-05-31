interface Source {
  db: string;
  url?: string;
  allele_frequency?: number;
  pmids?: string[];
  [key: string]: unknown;
}

interface Props {
  source: Source;
}

export default function SourceBadge({ source }: Props) {
  const href =
    source.url ??
    (source.pmids?.length
      ? `https://pubmed.ncbi.nlm.nih.gov/?term=${source.pmids.join(",")}`
      : null);

  const label = [
    source.db,
    source.allele_frequency != null
      ? `AF: ${(source.allele_frequency * 100).toFixed(1)}%`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  const badge = (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium
                     bg-gray-800 text-gray-400 hover:bg-gray-700 transition-colors cursor-pointer">
      {label}
    </span>
  );

  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {badge}
    </a>
  ) : (
    badge
  );
}
