import { API_BASE_URL, isApiConfigured } from "./config";
import { ApiError } from "./types";

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | undefined;
  body?: unknown;
  signal?: AbortSignal | undefined;
}

/**
 * Thin, modular fetch wrapper. Every call goes through here so auth headers,
 * error normalisation and JSON handling live in a single place.
 */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  if (!isApiConfigured()) {
    throw new ApiError("API base URL is not configured (VITE_API_BASE_URL).", 0);
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };

  let response: Response;
  try {
    const init: RequestInit = {
      method: options.method ?? "GET",
      headers,
      // Auth lives in the backend: forward the session cookie, never a client token.
      credentials: "include",
    };
    if (options.body !== undefined) init.body = JSON.stringify(options.body);
    if (options.signal) init.signal = options.signal;
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Network error — the concierge service is unreachable.", 0);
  }

  if (response.status === 401 || response.status === 403) {
    throw new ApiError("Your session isn't authorised. Please sign in again.", response.status);
  }

  if (!response.ok) {
    let detail = "";
    try {
      const data = (await response.json()) as { message?: string; detail?: string };
      detail = data.message ?? data.detail ?? "";
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail || `Request failed with status ${response.status}.`, response.status);
  }

  return (await response.json()) as T;
}
