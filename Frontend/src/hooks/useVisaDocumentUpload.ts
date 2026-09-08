import { useCallback, useState } from "react";
import { toast } from "sonner";

import { validateFile } from "@/components/concierge/documents/fileRules";
import {
  getVisaCaseDetail,
  getVisaCases,
  uploadVisaDocuments,
  type VisaCaseDetail,
  type VisaUploadResponse,
} from "@/lib/api/visa";

export type VisaUploadState =
  | "loading"
  | "ready"
  | "uploading"
  | "no_case"
  | "error";

/**
 * The visa document window's state.
 *
 * Simpler than its school twin in two ways, both because of what HCS-11 offers. There is
 * one case per new joiner, so nothing to select between; and there is no way to delete a
 * document, so a wrong one is corrected by sending the right one, which is an ordinary
 * upload rather than a separate operation.
 */
export function useVisaDocumentUpload() {
  const [state, setState] = useState<VisaUploadState>("loading");
  const [stage, setStage] = useState<string | null>(null);
  const [caseData, setCaseData] = useState<VisaCaseDetail | null>(null);
  const [result, setResult] = useState<VisaUploadResponse | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (employeeId: string) => {
    setState("loading");
    setError(null);
    try {
      const cases = await getVisaCases(employeeId);
      // A new joiner has one visa case, for themself. If HCS-11 ever opens more, the
      // first is the one being worked on.
      const open = cases[0];
      if (!open) {
        setState("no_case");
        return;
      }
      setCaseData(await getVisaCaseDetail(open.case_id));
      setState("ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the visa service");
      setState("error");
    }
  }, []);

  const addFiles = useCallback((incoming: File[]) => {
    const good: File[] = [];
    for (const file of incoming) {
      const wrong = validateFile(file);
      if (wrong) toast.error(wrong);
      else good.push(file);
    }
    if (good.length) setSelectedFiles((existing) => [...existing, ...good]);
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((existing) => existing.filter((_, i) => i !== index));
  }, []);

  const upload = useCallback(async () => {
    if (!caseData || selectedFiles.length === 0) return;

    setState("uploading");
    setError(null);
    setStage(null);
    try {
      const uploaded = await uploadVisaDocuments(caseData.case.case_id, selectedFiles, {
        onStage: setStage,
      });
      setResult(uploaded);
      setSelectedFiles([]);

      // The upload's own answer already carries the checklist, so the window updates from
      // it rather than asking again.
      setCaseData((current) =>
        current
          ? {
              case: {
                ...current.case,
                case_status: uploaded.case_status ?? current.case.case_status,
                missing_documents: uploaded.documents
                  .filter((row) => !row.received)
                  .map((row) => row.kind),
              },
              documents: uploaded.documents,
            }
          : current
      );

      if (uploaded.status === "success") toast.success(uploaded.title);
      else if (uploaded.status === "needs_reupload") toast.warning(uploaded.title);
      else toast.info(uploaded.title);

      setState("ready");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Sending your documents failed";
      setError(message);
      toast.error(message);
      setState("ready");
    } finally {
      setStage(null);
    }
  }, [caseData, selectedFiles]);

  const reset = useCallback(() => {
    setSelectedFiles([]);
    setResult(null);
    setError(null);
    setStage(null);
  }, []);

  return {
    state,
    stage,
    caseData,
    result,
    selectedFiles,
    error,
    load,
    addFiles,
    removeFile,
    upload,
    reset,
  };
}
