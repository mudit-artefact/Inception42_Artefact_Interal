/**
 * HCS-11 Document Verification API client.
 *
 * Handles document uploads and verification status for the school
 * allowance verification workflow.
 */

import { API_BASE_URL, isApiConfigured } from "./config";

// ─── Types ─────────────────────────────────────────────────────────────────

export type UploadStatus =
  | "success"
  | "partial"
  | "needs_reupload"
  | "needs_review"
  | "incomplete"
  | "already_paid"
  | "error";

export interface DocumentStatus {
  kind: string;
  label: string;
  filename: string | null;
  received: boolean;
  has_issues: boolean;
  issue_message: string | null;
}

export interface UploadResponse {
  status: UploadStatus;
  title: string;
  message: string;
  documents: DocumentStatus[];
  issues: string[];
  missing_documents: string[];
  can_reupload: boolean;
  reupload_message: string | null;
  case_id: string | null;
  case_status: string | null;
  payment_amount: number | null;
  payment_status: string | null;
}

export interface CaseSummary {
  case_id: string;
  employee_id: string;
  employee_name: string;
  dependent_id: string;
  dependent_name: string;
  academic_year: string;
  case_status: string;
  submission_deadline: string;
  submitted_on: string | null;
  payment_status: string;
  awaiting_review: boolean;
}

export interface CaseDetail extends CaseSummary {
  documents: Array<{
    document_id: string;
    file_name: string;
    kind: string | null;
    kind_label: string | null;
    uploaded_at: string;
  }>;
  required_documents: Array<{
    kind: string;
    label: string;
    received: boolean;
    file_name: string | null;
  }>;
  missing_documents: string[];
  employee_issues: Array<{
    kind: string;
    title: string;
    what_to_do: string;
  }>;
}

export interface CaseDetailResponse {
  case: CaseDetail;
  status_message: string;
}

export interface UploadStage {
  text: string;
}

// ─── API Functions ─────────────────────────────────────────────────────────

/**
 * Check if HCS-11 service is available.
 */
export async function checkHCS11Health(): Promise<boolean> {
  if (!isApiConfigured()) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/hcs11/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/**
 * Get all verification cases for an employee.
 */
export async function getEmployeeCases(employeeId: string): Promise<CaseSummary[]> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/hcs11/cases?employee_id=${encodeURIComponent(employeeId)}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch cases: ${response.status}`);
  }

  const data = await response.json();
  return data.cases;
}

/**
 * Get employee's current active case.
 */
export async function getActiveCase(employeeId: string): Promise<CaseDetailResponse | null> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/hcs11/active-case?employee_id=${encodeURIComponent(employeeId)}`
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch active case: ${response.status}`);
  }

  const data = await response.json();
  return data; // Returns null if no active case
}

/**
 * Get full details of a case.
 */
export async function getCaseDetail(caseId: string): Promise<CaseDetailResponse> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const response = await fetch(`${API_BASE_URL}/api/v1/hcs11/cases/${encodeURIComponent(caseId)}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to fetch case: ${response.status}`);
  }

  return response.json();
}

/**
 * Upload documents to a case (non-streaming).
 */
export async function uploadDocuments(
  caseId: string,
  files: File[]
): Promise<UploadResponse> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(
    `${API_BASE_URL}/api/v1/hcs11/cases/${encodeURIComponent(caseId)}/documents`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Upload failed: ${response.status}`);
  }

  return response.json();
}

/**
 * Upload documents with streaming progress updates.
 */
export async function uploadDocumentsWithProgress(
  caseId: string,
  files: File[],
  handlers: {
    onStage?: (stage: UploadStage) => void;
    onComplete?: (result: UploadResponse) => void;
    onError?: (error: string) => void;
  }
): Promise<UploadResponse> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(
    `${API_BASE_URL}/api/v1/hcs11/cases/${encodeURIComponent(caseId)}/documents/stream`,
    {
      method: "POST",
      body: formData,
    }
  );

  if (!response.ok || !response.body) {
    throw new Error(`Upload request failed: ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffered = "";
  let result: UploadResponse | null = null;
  let errorMessage: string | null = null;

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
        handlers.onStage?.({ text: payload.text });
      } else if (name === "complete") {
        result = {
          status: payload.status as UploadStatus,
          title: payload.title,
          message: payload.message,
          documents: [],
          issues: payload.issues || [],
          missing_documents: payload.missing_documents || [],
          can_reupload: payload.can_reupload || false,
          reupload_message: payload.reupload_message,
          case_id: payload.case_id,
          case_status: payload.case_status,
          payment_amount: payload.payment_amount,
          payment_status: payload.payment_status,
        };
        handlers.onComplete?.(result);
      } else if (name === "error") {
        const err = String(payload.detail || "Upload failed");
        errorMessage = err;
        handlers.onError?.(err);
      }
    }
  }

  if (errorMessage) {
    throw new Error(errorMessage);
  }
  if (!result) {
    throw new Error("Upload ended without a result");
  }

  return result;
}

/**
 * Remove a document from a case.
 */
export async function removeDocument(
  caseId: string,
  documentId: string
): Promise<UploadResponse> {
  if (!isApiConfigured()) {
    throw new Error("API not configured");
  }

  const response = await fetch(
    `${API_BASE_URL}/api/v1/hcs11/cases/${encodeURIComponent(caseId)}/documents/${encodeURIComponent(documentId)}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Failed to remove document: ${response.status}`);
  }

  return response.json();
}
