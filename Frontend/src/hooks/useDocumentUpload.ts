import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  type CaseDetailResponse,
  type CaseSummary,
  type UploadResponse,
  type UploadStage,
  getEmployeeCases,
  getCaseDetail,
  uploadDocumentsWithProgress,
  removeDocument,
} from "@/lib/api/hcs11";

export type DocumentUploadStatus =
  | "idle"
  | "loading_cases"
  | "ready"
  | "uploading"
  | "success"
  | "error"
  | "no_case";

export interface UnrecognizedFile {
  document_id: string;
  file_name: string;
  detected_type: string | null;
}

export interface UseDocumentUploadReturn {
  status: DocumentUploadStatus;
  stage: string | null;
  allCases: CaseSummary[];
  caseData: CaseDetailResponse | null;
  uploadResult: UploadResponse | null;
  error: string | null;
  selectedFiles: File[];
  unrecognizedFiles: UnrecognizedFile[];
  isRemoving: string | null;
  loadCases: (employeeId: string) => Promise<void>;
  selectCase: (caseId: string) => Promise<void>;
  addFiles: (files: File[]) => void;
  removeFile: (index: number) => void;
  clearFiles: () => void;
  upload: () => Promise<void>;
  removeServerDocument: (documentId: string) => Promise<void>;
  refreshCase: () => Promise<void>;
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
  const [unrecognizedFiles, setUnrecognizedFiles] = useState<UnrecognizedFile[]>([]);
  const [isRemoving, setIsRemoving] = useState<string | null>(null);

  const loadCases = useCallback(async (employeeId: string) => {
    setStatus("loading_cases");
    setError(null);
    setCaseData(null);
    setAllCases([]);
    setUploadResult(null);
    setUnrecognizedFiles([]);

    try {
      console.log(`[HCS-11] Loading cases for employee: ${employeeId}`);
      const cases = await getEmployeeCases(employeeId);
      console.log(`[HCS-11] Found ${cases.length} total cases:`, cases);

      // Filter to active cases only (not fully paid)
      const activeCases = cases.filter(
        (c) => c.payment_status !== "Sent" && c.payment_status !== "Paid"
      );
      console.log(`[HCS-11] Active cases (not Sent/Paid): ${activeCases.length}`);

      if (activeCases.length === 0) {
        setStatus("no_case");
        if (cases.length > 0) {
          setError(`All ${cases.length} case(s) are already processed (Sent/Paid). No active cases to upload to.`);
        } else {
          setError(`No verification cases found for employee ${employeeId}. Please contact HC Services.`);
        }
        return;
      }

      setAllCases(activeCases);

      // Auto-select the first case and load its details
      const firstCase = activeCases[0]!;
      const details = await getCaseDetail(firstCase.case_id);
      setCaseData({ case: details.case, status_message: details.status_message });

      // Extract unrecognized files from case documents
      // HCS-11 marks unplaceable files with kind = null, undefined, empty, or "other"
      const unrecognized = details.case.documents
        .filter((doc) => !doc.kind || doc.kind === "other")
        .map((doc) => ({
          document_id: doc.document_id,
          file_name: doc.file_name,
          detected_type: doc.kind_label,
        }));
      setUnrecognizedFiles(unrecognized);

      setStatus("ready");
    } catch (e) {
      console.error("[HCS-11] Error loading cases:", e);
      const msg = e instanceof Error ? e.message : "Failed to load cases";
      // Check for common connection issues
      if (msg.includes("503") || msg.includes("unavailable")) {
        setError("HCS-11 document verification service is not available. Please ensure it's running on port 8001.");
      } else if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        setError("Cannot connect to the server. Please check if the backend is running.");
      } else {
        setError(msg);
      }
      setStatus("error");
    }
  }, []);

  const selectCase = useCallback(async (caseId: string) => {
    setStatus("loading_cases");
    setError(null);
    setUploadResult(null);
    setSelectedFiles([]);
    setUnrecognizedFiles([]);

    try {
      const details = await getCaseDetail(caseId);
      setCaseData({ case: details.case, status_message: details.status_message });

      // Extract unrecognized files
      // HCS-11 marks unplaceable files with kind = null, undefined, empty, or "other"
      const unrecognized = details.case.documents
        .filter((doc) => !doc.kind || doc.kind === "other")
        .map((doc) => ({
          document_id: doc.document_id,
          file_name: doc.file_name,
          detected_type: doc.kind_label,
        }));
      setUnrecognizedFiles(unrecognized);

      setStatus("ready");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load case details";
      setError(msg);
      setStatus("error");
    }
  }, []);

  const refreshCase = useCallback(async () => {
    if (!caseData) return;

    try {
      const details = await getCaseDetail(caseData.case.case_id);
      setCaseData({ case: details.case, status_message: details.status_message });

      // Update unrecognized files
      // HCS-11 marks unplaceable files with kind = null, undefined, empty, or "other"
      const unrecognized = details.case.documents
        .filter((doc) => !doc.kind || doc.kind === "other")
        .map((doc) => ({
          document_id: doc.document_id,
          file_name: doc.file_name,
          detected_type: doc.kind_label,
        }));
      setUnrecognizedFiles(unrecognized);
    } catch (e) {
      console.error("Failed to refresh case:", e);
    }
  }, [caseData]);

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
          onComplete: async (r) => {
            setUploadResult(r);
            setStage(null);
            setSelectedFiles([]);

            // Show toast notification based on result
            if (r.status === "success") {
              setStatus("success");
              toast.success("Documents received", {
                description: "Each one has been read. Your checklist shows what was recognised.",
              });
            } else if (r.issues.length > 0) {
              setStatus("ready");
              toast.warning("Documents need attention", {
                description: `${r.issues.length} issue(s) to fix. See details below.`,
              });
            } else {
              setStatus("ready");
              toast.info("Documents uploaded", {
                description: r.message,
              });
            }

            // Refresh case data to get updated state
            await refreshCase();
          },
          onError: (err) => {
            setError(err);
            setStage(null);
            setStatus("error");
            toast.error("Upload failed", {
              description: err,
            });
          },
        }
      );

      // Handle case where onComplete wasn't called
      if (result.status === "success") {
        setStatus("success");
      } else {
        setStatus("ready");
      }
      setUploadResult(result);
      setSelectedFiles([]);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Upload failed";
      setError(msg);
      setStatus("error");
      setStage(null);
      toast.error("Upload failed", {
        description: msg,
      });
    }
  }, [caseData, selectedFiles, refreshCase]);

  const removeServerDocument = useCallback(async (documentId: string) => {
    if (!caseData) return;

    setIsRemoving(documentId);
    try {
      await removeDocument(caseData.case.case_id, documentId);

      // Remove from local state
      setUnrecognizedFiles((prev) => prev.filter((f) => f.document_id !== documentId));

      // Refresh case data
      await refreshCase();

      toast.success("Document removed");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to remove document";
      toast.error("Failed to remove document", {
        description: msg,
      });
    } finally {
      setIsRemoving(null);
    }
  }, [caseData, refreshCase]);

  const reset = useCallback(() => {
    setStatus("idle");
    setStage(null);
    setAllCases([]);
    setCaseData(null);
    setUploadResult(null);
    setError(null);
    setSelectedFiles([]);
    setUnrecognizedFiles([]);
    setIsRemoving(null);
  }, []);

  return {
    status,
    stage,
    allCases,
    caseData,
    uploadResult,
    error,
    selectedFiles,
    unrecognizedFiles,
    isRemoving,
    loadCases,
    selectCase,
    addFiles,
    removeFile,
    clearFiles,
    upload,
    removeServerDocument,
    refreshCase,
    reset,
  };
}
