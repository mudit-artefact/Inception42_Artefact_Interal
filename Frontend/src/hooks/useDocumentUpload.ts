import { useCallback, useState } from "react";
import {
  type CaseDetailResponse,
  type CaseSummary,
  type UploadResponse,
  type UploadStage,
  getEmployeeCases,
  getCaseDetail,
  uploadDocumentsWithProgress,
} from "@/lib/api/hcs11";

export type DocumentUploadStatus =
  | "idle"
  | "loading_cases"
  | "ready"
  | "uploading"
  | "success"
  | "error"
  | "no_case";

export interface UseDocumentUploadReturn {
  status: DocumentUploadStatus;
  stage: string | null;
  // All cases for the employee (for child selector)
  allCases: CaseSummary[];
  // Currently selected case details
  caseData: CaseDetailResponse | null;
  uploadResult: UploadResponse | null;
  error: string | null;
  selectedFiles: File[];
  // Load all cases for an employee
  loadCases: (employeeId: string) => Promise<void>;
  // Select a specific case (child)
  selectCase: (caseId: string) => Promise<void>;
  addFiles: (files: File[]) => void;
  removeFile: (index: number) => void;
  clearFiles: () => void;
  upload: () => Promise<void>;
  reset: () => void;
}

const ALLOWED_TYPES = ["application/pdf", "image/png", "image/jpeg"];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function validateFile(file: File): string | null {
  if (!ALLOWED_TYPES.includes(file.type)) {
    return `"${file.name}" is not a supported format. Please use PDF, PNG, or JPEG.`;
  }
  if (file.size > MAX_FILE_SIZE) {
    const sizeMB = (file.size / 1024 / 1024).toFixed(1);
    return `"${file.name}" is too large (${sizeMB}MB). Maximum size is 10MB.`;
  }
  return null;
}

export function useDocumentUpload(): UseDocumentUploadReturn {
  const [status, setStatus] = useState<DocumentUploadStatus>("idle");
  const [stage, setStage] = useState<string | null>(null);
  const [allCases, setAllCases] = useState<CaseSummary[]>([]);
  const [caseData, setCaseData] = useState<CaseDetailResponse | null>(null);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const loadCases = useCallback(async (employeeId: string) => {
    setStatus("loading_cases");
    setError(null);
    setCaseData(null);
    setAllCases([]);
    setUploadResult(null);

    try {
      const cases = await getEmployeeCases(employeeId);

      // Filter to active cases only (not fully paid)
      const activeCases = cases.filter(
        (c) => c.payment_status !== "Sent" && c.payment_status !== "Paid"
      );

      if (activeCases.length === 0) {
        setStatus("no_case");
        setError("No active verification cases found. Please contact HC Services.");
        return;
      }

      setAllCases(activeCases);

      // Auto-select the first case and load its details
      const firstCase = activeCases[0]!;
      const details = await getCaseDetail(firstCase.case_id);
      setCaseData({ case: details.case, status_message: details.status_message });
      setStatus("ready");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load cases";
      setError(msg);
      setStatus("error");
    }
  }, []);

  const selectCase = useCallback(async (caseId: string) => {
    setStatus("loading_cases");
    setError(null);
    setUploadResult(null);
    setSelectedFiles([]);

    try {
      const details = await getCaseDetail(caseId);
      setCaseData({ case: details.case, status_message: details.status_message });
      setStatus("ready");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load case details";
      setError(msg);
      setStatus("error");
    }
  }, []);

  const addFiles = useCallback((files: File[]) => {
    const errors: string[] = [];
    const validFiles: File[] = [];

    for (const file of files) {
      const validationError = validateFile(file);
      if (validationError) {
        errors.push(validationError);
      } else {
        validFiles.push(file);
      }
    }

    if (errors.length > 0) {
      setError(errors.join("\n"));
    } else {
      setError(null);
    }

    setSelectedFiles((prev) => [...prev, ...validFiles]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
    setError(null);
  }, []);

  const clearFiles = useCallback(() => {
    setSelectedFiles([]);
    setError(null);
  }, []);

  const upload = useCallback(async () => {
    if (!caseData || selectedFiles.length === 0) {
      setError("No files selected or case not loaded");
      return;
    }

    setStatus("uploading");
    setStage("Validating files...");
    setError(null);
    setUploadResult(null);

    try {
      const result = await uploadDocumentsWithProgress(
        caseData.case.case_id,
        selectedFiles,
        {
          onStage: (s: UploadStage) => setStage(s.text),
          onComplete: (r) => {
            setUploadResult(r);
            setStage(null);
            if (r.status === "success") {
              setStatus("success");
              setSelectedFiles([]);
            } else {
              setStatus("ready");
              // Clear selected files after upload attempt so user can add new ones
              setSelectedFiles([]);
            }
          },
          onError: (err) => {
            setError(err);
            setStage(null);
            setStatus("error");
          },
        }
      );

      if (result.status === "success") {
        setStatus("success");
        setSelectedFiles([]);
      } else {
        setStatus("ready");
        // Clear selected files after upload attempt
        setSelectedFiles([]);
      }
      setUploadResult(result);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setError(msg);
      setStatus("error");
      setStage(null);
    }
  }, [caseData, selectedFiles]);

  const reset = useCallback(() => {
    setStatus("idle");
    setStage(null);
    setAllCases([]);
    setCaseData(null);
    setUploadResult(null);
    setError(null);
    setSelectedFiles([]);
  }, []);

  return {
    status,
    stage,
    allCases,
    caseData,
    uploadResult,
    error,
    selectedFiles,
    loadCases,
    selectCase,
    addFiles,
    removeFile,
    clearFiles,
    upload,
    reset,
  };
}
