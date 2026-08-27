export type ChatRole = "user" | "assistant";

export interface PolicySource {
  id?: string;
  title: string;
  source?: string;
  source_type?: "policy" | "database";
  table_name?: string;
  section?: string;
  page_number?: number;
  url?: string;
  snippet?: string;
  score?: number;
  language?: string;
  pdf_url?: string;
  has_image?: boolean;
}

export interface ChatRequest {
  message?: string;
  query?: string;
  conversation_id?: string | null;
  employee_id?: string;
  target_language?: string;
}

export interface ChatResponse {
  answer: string;
  sources: PolicySource[];
  conversation_id?: string;
  employee_profile?: EmployeeProfile;
  target_language?: string;
  latency_ms?: number;
  tokens_used?: number;
  intent?: string;
  rewritten_query?: string;
  confidence_score?: number;
}

export interface EvaluationReport {
  total_test_cases: number;
  intent_accuracy_pct: number;
  retrieval_recall_at_5_pct: number;
  abstain_accuracy_pct: number;
  faithfulness_score_pct: number;
  mrr_score: number;
  avg_latency_ms: number;
  ablation_study: {
    raw_query_recall_pct: number;
    rewritten_hybrid_recall_pct: number;
    improvement_delta_pct: number;
    hybrid_rrf_boost_pct: number;
  };
  category_breakdown: Record<string, { total: number; correct_intent: number; correct_retrieval: number }>;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  sources?: PolicySource[];
  feedback?: "up" | "down" | null;
  error?: string;
  intent?: string;
  rewritten_query?: string;
  confidence_score?: number;
}

export interface Conversation {
  /** Local, stable identifier used for UI routing/history. */
  id: string;
  /** conversation_id returned by the API, sent back on follow-up turns. */
  remoteId: string | null;
  title: string;
  updatedAt: string;
  messages: ChatMessage[];
}

export interface LeaveBalance {
  type: string;
  used: number;
  entitled: number;
  unit: string;
}

export interface EmployeeProfile {
  id: string;
  user_id?: string;
  name: string;
  name_ar?: string;
  jobTitle: string;
  role?: string;
  department: string;
  grade: string;
  manager: string;
  email?: string;
  balances: LeaveBalance[];
  policyLinks?: PolicySource[];
  annual_leave_balance?: number;
  sick_leave_balance?: number;
  carry_over_days?: number;
  probation_status?: string;
  years_of_service?: number;
  start_date?: string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

