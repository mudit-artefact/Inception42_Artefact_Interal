/**
 * Talking to the employment visa endpoints.
 *
 * Separate from the school client because the two answer different shapes, but the
 * request side is the same: multipart files, and a stream of progress events while
 * HCS-11 reads them.
 */

import { API_BASE_URL, isApiConfigured } from "./config";

/** One row of the checklist, worked out on the server rather than here. */
export interface VisaDocumentRow {
  kind: string;
  label: string;
  filename: string | null;
  received: boolean;
  has_issues: boolean;
  issue_message: string | null;
}

export interface VisaCase {
  case_id: string;
  employee_id: string;
  employee_name: string;
  plan_code: string | null;
  plan_name: string | null;
  case_status: string;
  route: string | null;
  submission_deadline: string | null;
  submitted_on: string | null;
  required_documents: string[];
  missing_documents: string[];
  problems: string[];
}

export interface VisaCaseDetail {
  case: VisaCase;
  documents: VisaDocumentRow[];
}

export type VisaUploadStatus =
  | "success"
  | "partial"
  | "needs_reupload"
  | "needs_review"
  | "incomplete"
  | "rejected"
  | "error";

export interface VisaUploadResponse {
  status: VisaUploadStatus;
  title: string;
  message: string;
  documents: VisaDocumentRow[];
  issues: string[];
  missing_documents: string[];
  can_reupload: boolean;
  reupload_message: string | null;
  case_id: string | null;
  case_status: string | null;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body?.detail === "string" ? body.detail : `Request failed (${response.status})`;
  } catch {
    return `Request failed (${response.status})`;
  }
}

export async function getVisaCases(employeeId: string): Promise<VisaCase[]> {
  if (!isApiConfigured()) throw new Error("API not configured");

  const response = await fetch(
    `${API_BASE_URL}/api/v1/visa/cases?employee_id=${encodeURIComponent(employeeId)}`
  );
  if (!response.ok) throw new Error(await readDetail(response));

  const body = await response.json();
  return body.cases ?? [];
}

export async function getVisaCaseDetail(caseId: string): Promise<VisaCaseDetail> {
  if (!isApiConfigured()) throw new Error("API not configured");

  const response = await fetch(
    `${API_BASE_URL}/api/v1/visa/cases/${encodeURIComponent(caseId)}`
  );
  if (!response.ok) throw new Error(await readDetail(response));

  return response.json();
}

/**
 * Send documents, reporting progress as HCS-11 reads them.
 *
 * The `complete` event carries every field the plain endpoint returns, checklist
 * included — so unlike the school client, nothing here has to invent an empty one.
 */
export async function uploadVisaDocuments(
  caseId: string,
  files: File[],
  handlers: {
    onStage?: (text: string) => void;
    onComplete?: (result: VisaUploadResponse) => void;
    onError?: (message: string) => void;
  }
): Promise<VisaUploadResponse> {
  if (!isApiConfigured()) throw new Error("API not configured");

  const body = new FormData();
  files.forEach((file) => body.append("files", file));

  const response = await fetch(
    `${API_BASE_URL}/api/v1/visa/cases/${encodeURIComponent(caseId)}/documents/stream`,
    { method: "POST", body }
  );

  if (!response.ok || !response.body) {
    throw new Error(await readDetail(response));
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let result: VisaUploadResponse | null = null;
  let failure: string | null = null;

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

      if (name === "stage") {
        handlers.onStage?.(payload.text);
      } else if (name === "complete") {
        result = payload as VisaUploadResponse;
        handlers.onComplete?.(result);
      } else if (name === "error") {
        failure = String(payload.detail || "Sending your documents failed");
        handlers.onError?.(failure);
      }
    }
  }

  if (failure) throw new Error(failure);
  if (!result) throw new Error("The upload ended without a result");
  return result;
}
