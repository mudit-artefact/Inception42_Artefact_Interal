export type ChatRole = "user" | "assistant";

export interface PolicySource {
  id?: string | undefined;
  title: string;
  source?: string | undefined;
  source_type?: "policy" | "database" | undefined;
  table_name?: string | undefined;
  section?: string | undefined;
  page_number?: number | undefined;
  url?: string | undefined;
  snippet?: string | undefined;
  score?: number | undefined;
  language?: string | undefined;
  pdf_url?: string | undefined;
  has_image?: boolean | undefined;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  [key: string]: unknown;
}

export interface ChartPayload {
  title?: string | undefined;
  type?: "bar" | "pie" | "line" | undefined;
  data: ChartDataPoint[];
  xAxisKey?: string | undefined;
  dataKey?: string | undefined;
  unit?: string | undefined;
}

export interface ChatRequest {
  message?: string | undefined;
  query?: string | undefined;
  conversation_id?: string | null | undefined;
  employee_id?: string | undefined;
  target_language?: string | undefined;
  // For clarification follow-up (ambiguous query handling)
  original_question?: string | null | undefined;
  user_clarification?: string | null | undefined;
}

export interface ActionPayload {
  action_type?: string | undefined;
  leave_type?: string | undefined;
  min_date?: string | undefined;
  start_date?: string | undefined;
  end_date?: string | undefined;
  pending_approvals?: any[] | undefined;
  approved_leave?: any | undefined;
  cases?: any[] | undefined;
  dependents?: any[] | undefined;
  [key: string]: any;
}

export interface ChatResponse {
  answer: string;
  sources: PolicySource[];
  conversation_id?: string | undefined;
  employee_profile?: EmployeeProfile | undefined;
  target_language?: string | undefined;
  latency_ms?: number | undefined;
  tokens_used?: number | undefined;
  intent?: string | undefined;
  rewritten_query?: string | undefined;
  confidence_score?: number | undefined;
  // Clarification handling (for ambiguous queries)
  is_awaiting_clarification?: boolean | undefined;
  original_question?: string | null | undefined;
  clarifying_question?: string | null | undefined;
  // Agentic Action handling
  action_payload?: ActionPayload | null | undefined;
  is_action_required?: boolean | undefined;
  chart?: ChartPayload | undefined;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  createdAt: string;
  sources?: PolicySource[] | undefined;
  feedback?: "up" | "down" | null | undefined;
  error?: string | undefined;
  intent?: string | undefined;
  rewritten_query?: string | undefined;
  confidence_score?: number | undefined;
  // Clarification handling
  is_awaiting_clarification?: boolean | undefined;
  original_question?: string | null | undefined;
  // Agentic Action handling
  action_payload?: ActionPayload | null | undefined;
  is_action_required?: boolean | undefined;
  chart?: ChartPayload | undefined;
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
  /** Sent by the API. Never derive it — entitled - used ignores carried-over days. */
  remaining: number;
  carry_over: number;
  year: number;
  unit: string;
}

export interface EmployeeProfile {
  id: string;
  user_id?: string | undefined;
  name: string;
  name_ar?: string | undefined;
  jobTitle: string;
  role?: string | undefined;
  department: string;
  grade: string;
  manager: string;
  email?: string | undefined;
  balances: LeaveBalance[];
  policyLinks?: PolicySource[] | undefined;
  annual_leave_balance?: number | undefined;
  sick_leave_balance?: number | undefined;
  carry_over_days?: number | undefined;
  probation_status?: string | undefined;
  years_of_service?: number | undefined;
  start_date?: string | undefined;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}
