"use client";

import { useState, type FormEvent } from "react";

interface Props {
  onAnalyze: (rsId: string) => void;
  disabled?: boolean;
}

const EXAMPLES = ["rs1051730", "rs429358", "rs7412", "rs1800562"];

export default function VariantInput({ onAnalyze, disabled = false }: Props) {
  const [value, setValue] = useState("");
  const [validationError, setValidationError] = useState("");

  const validate = (v: string): boolean => /^rs\d+$/i.test(v.trim());

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!validate(trimmed)) {
      setValidationError('Must be in rsID format — e.g. "rs1051730" (starts with "rs" then digits)');
      return;
    }
    setValidationError("");
    onAnalyze(trimmed.toLowerCase());
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            if (validationError) setValidationError("");
          }}
          placeholder='Enter rsID — e.g. "rs1051730"'
          disabled={disabled}
          className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-lg
                     text-gray-100 placeholder-gray-600
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent
                     disabled:opacity-50"
          aria-label="Genomic variant rsID"
        />
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
            onClick={() => { setValue(ex); setValidationError(""); }}
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
