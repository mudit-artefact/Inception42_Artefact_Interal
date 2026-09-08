import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Circle,
  Clock,
  FileText,
  Loader2,
  Trash2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import type { CaseDetail } from "@/lib/api/hcs11";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";

interface DocumentUploadProps {
  employeeId: string;
  onClose: () => void;
}

type ProgressStep = "documents" | "checks" | "decision" | "payment";

interface StepConfig {
  key: ProgressStep;
  label: string;
  sublabel: string;
}

const PROGRESS_STEPS: StepConfig[] = [
  { key: "documents", label: "Documents received", sublabel: "" },
  { key: "checks", label: "Checks completed", sublabel: "" },
  { key: "decision", label: "Decision", sublabel: "With HC Services" },
  { key: "payment", label: "Paid through payroll", sublabel: "Approved claims only" },
];

function getStepStatus(
  step: ProgressStep,
  caseStatus: string | null,
  paymentStatus: string | null,
  allDocsReceived: boolean,
  hasIssues: boolean
): "complete" | "warning" | "active" | "pending" {
  switch (step) {
    case "documents":
      if (!allDocsReceived) return "active";
      // All received but some have issues = warning
      return hasIssues ? "warning" : "complete";
    case "checks":
      if (!allDocsReceived) return "pending";
      if (caseStatus === "Under Review" || caseStatus === "Pending Review") return "active";
      if (caseStatus === "Approved" || caseStatus === "Rejected") return "complete";
      return "pending";
    case "decision":
      if (caseStatus === "Approved") return "complete";
      if (caseStatus === "Rejected") return "complete";
      if (caseStatus === "Under Review") return "active";
      return "pending";
    case "payment":
      if (paymentStatus === "Paid" || paymentStatus === "Sent") return "complete";
      if (paymentStatus === "Pending" && caseStatus === "Approved") return "active";
      return "pending";
    default:
      return "pending";
  }
}

interface DocumentIssue {
  title: string;
  message: string;
  documents: string[];      // File names
  document_ids: string[];   // Document IDs
}

/**
 * Get issues for a specific document by its document_id.
 * Uses employee_issues from the API which already has proper document attribution.
 */
function getDocumentIssuesByDocId(
  caseData: CaseDetail,
  documentId: string
): DocumentIssue[] {
  const issues: DocumentIssue[] = [];

  for (const issue of caseData.employee_issues || []) {
    // Check if this issue applies to this document
    if (issue.document_ids?.includes(documentId)) {
      issues.push({
        title: issue.title,
        message: issue.what_to_do,
        documents: issue.documents || [],
        document_ids: issue.document_ids || [],
      });
    }
  }

  return issues;
}

/**
 * Get issues for a document kind by finding the document_id for that kind first.
 */
function getDocumentIssues(
  caseData: CaseDetail,
  docKind: string
): DocumentIssue[] {
  // Find the document_id for this kind
  const doc = caseData.documents.find((d) => d.kind === docKind);
  if (!doc) return [];

  return getDocumentIssuesByDocId(caseData, doc.document_id);
}

function getDocumentByKind(
  caseData: CaseDetail,
  docKind: string
): { document_id: string; file_name: string } | null {
  const doc = caseData.documents.find((d) => d.kind === docKind);
  return doc ? { document_id: doc.document_id, file_name: doc.file_name } : null;
}

function ProgressTracker({
  caseStatus,
  paymentStatus,
  allDocsReceived,
  receivedCount,
  totalCount,
  issueCount,
}: {
  caseStatus: string | null;
  paymentStatus: string | null;
  allDocsReceived: boolean;
  receivedCount: number;
  totalCount: number;
  issueCount: number;
}) {
  const hasIssues = issueCount > 0;

  return (
    <div className="space-y-2">
      {PROGRESS_STEPS.map((step) => {
        const status = getStepStatus(step.key, caseStatus, paymentStatus, allDocsReceived, hasIssues);
        const isComplete = status === "complete";
        const isWarning = status === "warning";
        const isActive = status === "active";

        let sublabel = step.sublabel;
        let sublabel2: string | null = null;  // Second line for warnings
        if (step.key === "documents") {
          sublabel = `${receivedCount} of ${totalCount} received`;
          if (isWarning) {
            sublabel2 = `${issueCount} need${issueCount === 1 ? "s" : ""} attention`;
          }
        } else if (step.key === "checks" && isComplete) {
          sublabel = "Done";
        } else if (step.key === "decision" && caseStatus === "Approved") {
          sublabel = "Approved";
          sublabel2 = "Finance will confirm";
        } else if (step.key === "decision" && caseStatus === "Rejected") {
          sublabel = "Rejected";
        }

        return (
          <div key={step.key} className="flex items-start gap-2">
            <div className="mt-0.5">
              {isComplete ? (
                <div className="size-4 rounded-full bg-green-500 flex items-center justify-center">
                  <CheckCircle2 className="size-3 text-white" />
                </div>
              ) : isWarning ? (
                <div className="size-4 rounded-full bg-amber-500 flex items-center justify-center">
                  <AlertTriangle className="size-3 text-white" />
                </div>
              ) : isActive ? (
                <div className="size-4 rounded-full bg-pink flex items-center justify-center">
                  <Circle className="size-2 text-white fill-white" />
                </div>
              ) : (
                <div className="size-4 rounded-full border-2 border-muted-foreground/30" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className={`text-xs font-medium ${
                isComplete ? "text-green-700" :
                isWarning ? "text-amber-700" :
                isActive ? "text-foreground" :
                "text-muted-foreground"
              }`}>
                {step.label}
              </p>
              {sublabel && (
                <p className="text-[10px] text-muted-foreground truncate">
                  {sublabel}
                </p>
              )}
              {sublabel2 && (
                <p className={`text-[10px] truncate ${isWarning ? "text-amber-600" : "text-muted-foreground"}`}>
                  {sublabel2}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function DocumentUpload({ employeeId, onClose }: DocumentUploadProps) {
  const {
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
    upload,
    removeServerDocument,
    reset,
  } = useDocumentUpload();

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadCases(employeeId);
  }, [employeeId, loadCases]);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const files = Array.from(e.dataTransfer.files);
      addFiles(files);
    },
    [addFiles]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    addFiles(files);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleUpload = async () => {
    await upload();
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  const handleChildChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const caseId = e.target.value;
    if (caseId) {
      selectCase(caseId);
    }
  };

  // Check if all required documents are received
  const allDocumentsReceived = caseData?.case.required_documents.every((doc) => doc.received) ?? false;
  const receivedCount = caseData?.case.required_documents.filter((doc) => doc.received).length ?? 0;
  const totalCount = caseData?.case.required_documents.length ?? 0;
  const isUploading = status === "uploading";

  // Count documents with issues (not total issues)
  const totalIssueCount = useMemo(() => {
    if (!caseData) return 0;
    let count = 0;
    for (const doc of caseData.case.required_documents) {
      if (getDocumentIssues(caseData.case, doc.kind).length > 0) {
        count += 1;
      }
    }
    return count;
  }, [caseData]);

  // Total number of employee issues (for display)
  const totalEmployeeIssues = caseData?.case.employee_issues?.length ?? 0;

  const hasIssues = totalIssueCount > 0 || totalEmployeeIssues > 0;

  // Loading state
  if (status === "loading_cases") {
    return (
      <Card className="w-full max-w-3xl mx-auto">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-pink" />
          <p className="mt-3 text-sm text-muted-foreground">Loading your verification cases...</p>
        </CardContent>
      </Card>
    );
  }

  // No case found or error
  if (status === "no_case" || status === "error") {
    return (
      <Card className="w-full max-w-3xl mx-auto">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold">Document Verification</CardTitle>
            <Button variant="ghost" size="icon" onClick={handleClose}>
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-8">
          <AlertTriangle className="size-10 text-amber-500" />
          <p className="mt-3 text-sm text-center text-muted-foreground max-w-md">
            {error || "No active verification case found for this academic year."}
          </p>
          <p className="mt-2 text-xs text-center text-muted-foreground">
            Employee ID: {employeeId}
          </p>
          <div className="flex gap-2 mt-4">
            <Button variant="outline" onClick={() => loadCases(employeeId)}>
              Retry
            </Button>
            <Button variant="ghost" onClick={handleClose}>
              Close
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Main upload interface with progress sidebar
  return (
    <Card className="w-full max-w-3xl mx-auto max-h-[85vh] flex flex-col">
      <CardHeader className="pb-3 shrink-0 border-b">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <CardTitle className="text-base font-semibold">
              School Verification Documents
            </CardTitle>

            {/* Child selector and info */}
            <div className="mt-2 flex items-center gap-3 flex-wrap">
              {allCases.length > 1 ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">Child:</span>
                  <div className="relative">
                    <select
                      value={caseData?.case.case_id || ""}
                      onChange={handleChildChange}
                      disabled={isUploading}
                      className="appearance-none bg-muted text-sm font-medium pl-3 pr-8 py-1.5 rounded-md border-0 focus:ring-2 focus:ring-pink cursor-pointer disabled:opacity-50"
                    >
                      {allCases.map((c) => (
                        <option key={c.case_id} value={c.case_id}>
                          {c.dependent_name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                  </div>
                </div>
              ) : caseData ? (
                <span className="text-sm font-medium">{caseData.case.dependent_name}</span>
              ) : null}

              {caseData && (
                <>
                  <span className="text-xs text-muted-foreground">
                    {caseData.case.academic_year}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Due: {caseData.case.submission_deadline}
                  </span>
                </>
              )}
            </div>
          </div>
          <Button variant="ghost" size="icon" onClick={handleClose} disabled={isUploading}>
            <X className="size-4" />
          </Button>
        </div>
      </CardHeader>

      <div className="flex flex-1 overflow-hidden">
        {/* Main content area */}
        <CardContent className="flex-1 space-y-4 overflow-y-auto p-4">
          {/* Required documents checklist */}
          {caseData && caseData.case.required_documents.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  What your claim needs
                </p>
                <span className="text-xs text-muted-foreground">
                  {receivedCount} of {totalCount} received
                </span>
              </div>
              <div className="border rounded-lg divide-y">
                {caseData.case.required_documents.map((doc) => {
                  const docIssues = getDocumentIssues(caseData.case, doc.kind);
                  const docHasIssues = docIssues.length > 0;
                  const docInfo = getDocumentByKind(caseData.case, doc.kind);

                  return (
                    <div
                      key={doc.kind}
                      className={`p-3 ${docHasIssues ? "bg-amber-500/5" : ""}`}
                    >
                      <div className="flex items-start gap-3">
                        {doc.received ? (
                          docHasIssues ? (
                            <AlertTriangle className="size-4 text-amber-500 shrink-0 mt-0.5" />
                          ) : (
                            <CheckCircle2 className="size-4 text-green-500 shrink-0 mt-0.5" />
                          )
                        ) : (
                          <Clock className="size-4 text-muted-foreground/50 shrink-0 mt-0.5" />
                        )}
                        <div className="flex-1 min-w-0">
                          <p className={`text-sm font-medium ${
                            docHasIssues ? "text-amber-700" : doc.received ? "text-foreground" : "text-muted-foreground"
                          }`}>
                            {doc.label}
                          </p>
                          {doc.file_name && (
                            <p className="text-xs text-muted-foreground truncate">{doc.file_name}</p>
                          )}
                          {/* Show issues inline under the document */}
                          {docHasIssues && (
                            <div className="mt-2 space-y-1">
                              {docIssues.map((issue, idx) => (
                                <p key={idx} className="text-xs text-amber-600">
                                  <span className="font-medium">{issue.title}:</span> {issue.message}
                                </p>
                              ))}
                            </div>
                          )}
                        </div>
                        {/* Remove button for documents with issues */}
                        {docHasIssues && docInfo && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="shrink-0 text-amber-600 hover:text-amber-700 hover:bg-amber-100"
                            onClick={() => removeServerDocument(docInfo.document_id)}
                            disabled={isRemoving === docInfo.document_id || isUploading}
                          >
                            {isRemoving === docInfo.document_id ? (
                              <Loader2 className="size-3 animate-spin" />
                            ) : (
                              <X className="size-4" />
                            )}
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Success message when all documents received */}
          {allDocumentsReceived && !hasIssues && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-green-500/30 bg-green-500/5">
              <CheckCircle2 className="size-4 text-green-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-green-700">Everything we need is here</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Received {new Date().toLocaleDateString()} · reference {caseData?.case.case_id}
                </p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="ml-auto shrink-0"
                onClick={() => fileInputRef.current?.click()}
                disabled={isUploading}
              >
                Send another
              </Button>
            </div>
          )}

          {/* Issues summary banner - only when there are per-document issues */}
          {totalIssueCount > 0 && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-amber-500/30 bg-amber-500/5">
              <AlertTriangle className="size-4 text-amber-500 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-700">
                  {totalIssueCount === 1 ? "1 document needs attention" : `${totalIssueCount} documents need attention`}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Click the X next to a document to remove it, then upload a corrected version.
                </p>
              </div>
            </div>
          )}

          {/* Unrecognized files - can be removed */}
          {unrecognizedFiles.length > 0 && (
            <div className="space-y-2 p-3 rounded-lg border border-rose-500/30 bg-rose-500/5">
              <div className="flex items-start gap-2">
                <AlertTriangle className="size-4 text-rose-500 mt-0.5 shrink-0" />
                <div>
                  <p className="text-sm font-medium text-rose-700">
                    We could not place {unrecognizedFiles.length === 1 ? "one of your files" : `${unrecognizedFiles.length} of your files`}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {unrecognizedFiles.length === 1 ? "It is" : "They are"} not one of the documents this claim needs, so {unrecognizedFiles.length === 1 ? "it does" : "they do"} not count towards the list above.
                  </p>
                </div>
              </div>
              <div className="space-y-1 pt-2">
                {unrecognizedFiles.map((file) => (
                  <div
                    key={file.document_id}
                    className="flex items-center justify-between p-2 rounded-md bg-background"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="size-4 text-rose-500 shrink-0" />
                      <div className="min-w-0">
                        <p className="text-xs font-medium truncate">{file.file_name}</p>
                        {file.detected_type && (
                          <p className="text-[10px] text-muted-foreground">
                            Looks like: {file.detected_type}
                          </p>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="shrink-0 text-xs"
                      onClick={() => removeServerDocument(file.document_id)}
                      disabled={isRemoving === file.document_id}
                    >
                      {isRemoving === file.document_id ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <>
                          <Trash2 className="size-3 mr-1" />
                          Remove
                        </>
                      )}
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="flex items-start gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/5">
              <XCircle className="size-4 text-destructive mt-0.5 shrink-0" />
              <p className="text-xs text-destructive whitespace-pre-line">{error}</p>
            </div>
          )}

          {/* Upload area - always visible */}
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              PDF, JPG or PNG, up to 10 MB each. Arabic documents are fine, and the order does not matter — each one is recognised from what is printed on it.
            </p>

            {/* Drop zone */}
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => !isUploading && fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg transition-colors ${
                isUploading
                  ? "border-muted-foreground/20 bg-muted/50 cursor-not-allowed"
                  : "border-muted-foreground/25 cursor-pointer hover:border-pink/50 hover:bg-pink/5"
              }`}
            >
              {isUploading ? (
                <>
                  <Loader2 className="size-8 text-pink animate-spin" />
                  <p className="mt-2 text-sm font-medium">{stage || "Processing..."}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    This may take up to a minute while we verify your documents
                  </p>
                  <Progress value={undefined} className="h-1 w-full max-w-xs mt-3" />
                </>
              ) : (
                <>
                  <Upload className="size-8 text-muted-foreground/50" />
                  <p className="mt-2 text-sm font-medium">
                    Drop files here or click to browse
                  </p>
                </>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                disabled={isUploading}
              />
            </div>
          </div>

          {/* Selected files pending upload */}
          {selectedFiles.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                Ready to upload ({selectedFiles.length})
              </p>
              <div className="space-y-1">
                {selectedFiles.map((file, index) => (
                  <div
                    key={`${file.name}-${index}`}
                    className="flex items-center justify-between p-2 rounded-md bg-muted"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="size-4 text-pink shrink-0" />
                      <span className="text-xs truncate">{file.name}</span>
                      <span className="text-[10px] text-muted-foreground shrink-0">
                        ({(file.size / 1024).toFixed(0)} KB)
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-6"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile(index);
                      }}
                      disabled={isUploading}
                    >
                      <X className="size-3" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>

        {/* Progress sidebar */}
        {caseData && (
          <div className="w-48 shrink-0 border-l bg-muted/30 p-4 overflow-y-auto">
            <ProgressTracker
              caseStatus={caseData.case.case_status}
              paymentStatus={caseData.case.payment_status}
              allDocsReceived={allDocumentsReceived}
              receivedCount={receivedCount}
              totalCount={totalCount}
              issueCount={totalIssueCount}
            />
          </div>
        )}
      </div>

      {/* Fixed footer with action buttons */}
      <div className="shrink-0 p-4 pt-3 border-t bg-card">
        <div className="flex gap-2">
          <Button variant="outline" className="flex-1" onClick={handleClose} disabled={isUploading}>
            {allDocumentsReceived && !hasIssues ? "Close" : "Cancel"}
          </Button>
          {selectedFiles.length > 0 && (
            <Button
              className="flex-1 bg-pink hover:bg-pink/90"
              disabled={isUploading}
              onClick={handleUpload}
            >
              {isUploading ? (
                <>
                  <Loader2 className="size-4 mr-2 animate-spin" />
                  Uploading...
                </>
              ) : (
                <>
                  <Upload className="size-4 mr-2" />
                  Upload ({selectedFiles.length})
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
