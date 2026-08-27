import { apiRequest } from "./client";
import { isApiConfigured } from "./config";
import { mockChat } from "./mock";
import type { ChatRequest, ChatResponse, EvaluationReport } from "./types";

/**
 * Send chat message to backend /api/v1/hcs01/query (or fallback to mock data).
 */
export async function sendChatMessage(
  message: string,
  conversationId: string | null,
  options?: { signal?: AbortSignal; employeeId?: string | null; targetLanguage?: "en" | "ar" },
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
