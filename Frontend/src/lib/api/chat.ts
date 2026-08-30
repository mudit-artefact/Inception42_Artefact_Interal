import { apiRequest } from "./client";
import { API_BASE_URL, isApiConfigured } from "./config";
import { mockChat } from "./mock";
import type { ChatRequest, ChatResponse, EvaluationReport } from "./types";

/**
 * Send chat message to backend /api/v1/hcs01/query (or fallback to mock data).
 */
export async function sendChatMessage(
  message: string,
  conversationId: string | null,
  options?: {
    signal?: AbortSignal;
    employeeId?: string | null;
    targetLanguage?: "en" | "ar";
    // For clarification follow-up
    originalQuestion?: string | null;
    userClarification?: string | null;
  },
): Promise<ChatResponse> {
  if (!isApiConfigured()) {
    return mockChat(message, conversationId, options?.employeeId ?? null);
  }

  const payload: ChatRequest = {
    message,
    query: message,
    conversation_id: conversationId,
    employee_id: options?.employeeId ?? "EMP001",
    target_language: options?.targetLanguage,
    // Include clarification data if provided
    original_question: options?.originalQuestion,
    user_clarification: options?.userClarification,
  };

  try {
    const data = await apiRequest<ChatResponse>("/api/v1/hcs01/query", {
      method: "POST",
      body: payload,
      ...(options?.signal ? { signal: options.signal } : {}),
    });

    return {
      answer: data.answer ?? "",
      sources: Array.isArray(data.sources)
        ? data.sources.map((s) => ({
            ...s,
            title: s.title || s.source || "Source",
            source_type: s.source_type || (s.pdf_url ? "policy" : "database"),
            table_name: s.table_name,
            snippet: s.snippet || "",
            url: s.pdf_url || s.url || "#",
            pdf_url: s.pdf_url,
            page_number: s.page_number,
            has_image: s.has_image || false,
          }))
        : [],
      conversation_id: data.conversation_id ?? conversationId ?? "",
      employee_profile: data.employee_profile,
      target_language: data.target_language,
      latency_ms: data.latency_ms,
      tokens_used: data.tokens_used,
      intent: data.intent,
      rewritten_query: data.rewritten_query,
      confidence_score: data.confidence_score,
      // Clarification handling
      is_awaiting_clarification: data.is_awaiting_clarification ?? false,
      original_question: data.original_question,
      clarifying_question: data.clarifying_question,
    };
  } catch (err) {
    console.warn("Backend chat request error:", err);
    throw err;
  }
}

/**
 * Fetch automated benchmark evaluation report from /api/v1/hcs01/eval
 */
export async function fetchEvaluationReport(): Promise<EvaluationReport> {
  return apiRequest<EvaluationReport>("/api/v1/hcs01/eval", {
    method: "GET",
  });
}

/** One step of the workflow, as the interface shows it while the answer is worked out. */
export interface ChatStage {
  step: string;
  text: string;
  found?: string[];
}

/**
 * Ask a question and watch the answer being worked out.
 *
 * Answers take most of a minute, and the interface had nothing to show for any of it.
 * The server sends a line per step it finishes — the record read, the documents searched,
 * the clauses found, the figures checked — then the answer.
 *
 * The answer arrives only once the server has checked it, so nothing shown here is ever
 * taken back. `fetch` rather than `EventSource` because the question goes in a POST body
 * and EventSource can only GET.
 */
export async function streamChatMessage(
  message: string,
  conversationId: string | null,
  handlers: {
    onStage?: (stage: ChatStage) => void;
    onDelta?: (delta: string) => void;
  },
  options?: {
    signal?: AbortSignal;
    employeeId?: string | null;
    targetLanguage?: "en" | "ar";
  },
): Promise<ChatResponse> {
  if (!isApiConfigured()) {
    return mockChat(message, conversationId, options?.employeeId ?? null);
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/hcs01/query/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      query: message,
      conversation_id: conversationId,
      employee_id: options?.employeeId ?? "EMP001",
      target_language: options?.targetLanguage,
    }),
    ...(options?.signal ? { signal: options.signal } : {}),
  });

  if (!response.ok || !response.body) {
    throw new Error(`Chat request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let finished: ChatResponse | null = null;
  let failure: string | null = null;

  // Events are separated by a blank line, so a chunk that splits one mid-way waits in
  // `buffered` until the rest of it arrives.
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffered += decoder.decode(value, { stream: true });

    const blocks = buffered.split("\n\n");
    buffered = blocks.pop() ?? "";

    for (const block of blocks) {
      const name = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
      const raw = block.match(/^data:\s*([\s\S]+)$/m)?.[1];
      if (!name || !raw) continue;

      const payload = JSON.parse(raw);
      if (name === "stage") handlers.onStage?.(payload as ChatStage);
      else if (name === "answer") handlers.onDelta?.(payload.delta as string);
      else if (name === "done") finished = normaliseChatResponse(payload, conversationId);
      else if (name === "error") failure = payload.detail ?? "Something went wrong.";
    }
  }

  if (failure) throw new Error(failure);
  if (!finished) throw new Error("The answer ended before it was finished.");
  return finished;
}

/** The wire shape, as the interface expects it. Shared by both routes so they cannot differ. */
function normaliseChatResponse(data: any, conversationId: string | null): ChatResponse {
  return {
    answer: data.answer ?? "",
    sources: Array.isArray(data.sources)
      ? data.sources.map((s: any) => ({
          ...s,
          title: s.title || s.source || "Source",
          source_type: s.source_type || (s.pdf_url ? "policy" : "database"),
          table_name: s.table_name,
          snippet: s.snippet || "",
          url: s.pdf_url || s.url || "#",
          pdf_url: s.pdf_url,
          page_number: s.page_number,
          has_image: s.has_image || false,
        }))
      : [],
    conversation_id: data.conversation_id ?? conversationId ?? "",
    employee_profile: data.employee_profile,
    target_language: data.target_language,
    latency_ms: data.latency_ms,
    tokens_used: data.tokens_used,
    intent: data.intent,
    rewritten_query: data.rewritten_query,
    confidence_score: data.confidence_score,
    is_awaiting_clarification: data.is_awaiting_clarification ?? false,
    original_question: data.original_question,
    clarifying_question: data.clarifying_question,
  };
}
