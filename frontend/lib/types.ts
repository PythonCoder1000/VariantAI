export interface VariantReport {
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

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  /** Transient: true while the assistant message is still streaming. */
  pending?: boolean;
}

export type SessionStatus = "analyzing" | "complete" | "error" | "unknown";

export interface ChatSession {
  id: string;
  variantId: string;
  status: SessionStatus;
  report: VariantReport | null;
  error: string | null;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

export interface MemoryItem {
  id: string;
  text: string;
  created_at: number;
}
