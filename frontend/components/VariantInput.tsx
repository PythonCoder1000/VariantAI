"use client";

import { useRef, useState, type FormEvent } from "react";

interface Props {
  onAnalyze: (rsId: string) => void;
  disabled?: boolean;
}

const EXAMPLES = ["rs1051730", "rs429358", "rs7412", "rs1800562"];

export default function VariantInput({ onAnalyze, disabled = false }: Props) {
  const [value, setValue] = useState("");
  const [validationError, setValidationError] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const validate = (v: string): boolean => /^rs\d+$/i.test(v.trim());

  const fetchSuggestions = (q: string) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!/^rs\d{2,}/i.test(q)) {
      setSuggestions([]);
      setShowDropdown(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
        const resp = await fetch(`${apiUrl}/api/suggest?q=${encodeURIComponent(q)}`);
        const data = await resp.json();
        const suggs: string[] = (data.suggestions ?? []).filter(
          (s: string) => s.toLowerCase() !== q.toLowerCase()
        );
        setSuggestions(suggs);
        setShowDropdown(suggs.length > 0);
      } catch {
        setSuggestions([]);
        setShowDropdown(false);
      }
    }, 300);
  };

  const handleChange = (v: string) => {
    setValue(v);
    if (validationError) setValidationError("");
    fetchSuggestions(v.trim());
  };

  const selectSuggestion = (s: string) => {
    setValue(s);
    setSuggestions([]);
    setShowDropdown(false);
    setValidationError("");
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    setShowDropdown(false);
    if (!validate(trimmed)) {
      setValidationError('Must be in rsID format — e.g. "rs1051730" (starts with "rs" then digits)');
      return;
    }
    setValidationError("");
    onAnalyze(trimmed.toLowerCase());
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 120)}
            onFocus={() => suggestions.length > 0 && setShowDropdown(true)}
            placeholder='Enter rsID — e.g. "rs1051730"'
            disabled={disabled}
            autoComplete="off"
            className="w-full px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg
                       text-gray-100 placeholder-gray-600
                       focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                       disabled:opacity-50"
            aria-label="Genomic variant rsID"
            aria-autocomplete="list"
            aria-expanded={showDropdown}
          />

          {/* Autocomplete dropdown */}
          {showDropdown && suggestions.length > 0 && (
            <ul
              role="listbox"
              className="absolute top-full left-0 right-0 z-10 mt-1 overflow-hidden
                         rounded-lg border border-gray-700 bg-gray-900 shadow-xl shadow-black/40"
            >
              {suggestions.map((s) => (
                <li key={s} role="option" aria-selected={false}>
                  <button
                    type="button"
                    onMouseDown={(e) => {
                      e.preventDefault(); // prevent input blur before click registers
                      selectSuggestion(s);
                    }}
                    className="w-full px-4 py-2 text-left text-sm text-gray-300
                               hover:bg-gray-800 transition-colors"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex items-center justify-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg font-medium
                     hover:bg-blue-500 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed
                     transition-all duration-150"
        >
          {disabled && (
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
          )}
          {disabled ? "Analyzing…" : "Analyze"}
        </button>
      </div>

      {validationError && (
        <p className="mt-2 text-sm text-red-400" role="alert">{validationError}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-sm text-gray-600">Try:</span>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => { setValue(ex); setValidationError(""); setShowDropdown(false); }}
            disabled={disabled}
            className="text-sm text-blue-400 hover:underline disabled:opacity-40"
          >
            {ex}
          </button>
        ))}
      </div>
    </form>
  );
}
