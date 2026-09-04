import { useCallback, useEffect, useRef } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Clock,
  FileText,
  Loader2,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { useDocumentUpload } from "@/hooks/useDocumentUpload";

interface DocumentUploadProps {
  employeeId: string;
  onClose: () => void;
  onComplete?: (childName: string) => void;
}

export function DocumentUpload({ employeeId, onClose, onComplete }: DocumentUploadProps) {
  const {
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
    upload,
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

  // Loading state
  if (status === "loading_cases") {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-pink" />
          <p className="mt-3 text-sm text-muted-foreground">Loading your verification cases...</p>
        </CardContent>
      </Card>
    );
  }

  // No case found
  if (status === "no_case") {
    return (
      <Card className="w-full max-w-2xl mx-auto">
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
          <p className="mt-3 text-sm text-center text-muted-foreground">
            No active verification case found for this academic year.
            <br />
            Please contact HC Services if you believe this is an error.
          </p>
          <Button variant="outline" className="mt-4" onClick={handleClose}>
            Close
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Success state - all documents verified
  if (status === "success" && uploadResult) {
    const childName = caseData?.case.dependent_name || "your child";

    // Auto-close after showing success briefly
    setTimeout(() => {
      onComplete?.(childName);
    }, 100);

    return (
      <Card className="w-full max-w-2xl mx-auto border-green-500/30 bg-green-500/5">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-5 text-green-500" />
              <CardTitle className="text-base font-semibold text-green-700">
                {uploadResult.title}
              </CardTitle>
            </div>
            <Button variant="ghost" size="icon" onClick={handleClose}>
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">{uploadResult.message}</p>

          {uploadResult.payment_amount && (
            <div className="flex items-center justify-between p-3 rounded-lg bg-green-500/10">
              <span className="text-sm font-medium">Approved Amount</span>
              <span className="text-lg font-semibold text-green-700">
                AED {uploadResult.payment_amount.toLocaleString()}
              </span>
            </div>
          )}

          {uploadResult.case_id && (
            <p className="text-xs text-muted-foreground">Reference: {uploadResult.case_id}</p>
          )}

          <Button className="w-full" onClick={() => { onComplete?.(childName); }}>
            Done
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Uploading state
  if (status === "uploading") {
    return (
      <Card className="w-full max-w-2xl mx-auto">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold">Uploading Documents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col items-center py-8">
            <Loader2 className="size-10 animate-spin text-pink" />
            <p className="mt-4 text-sm font-medium">{stage || "Processing..."}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              This may take up to a minute while we verify your documents
            </p>
          </div>
          <Progress value={undefined} className="h-1" />
        </CardContent>
      </Card>
    );
  }

  // Count how many documents still need to be uploaded
  const missingCount = caseData?.case.required_documents.filter((doc) => !doc.received).length ?? 0;
  const hasIssues = uploadResult && uploadResult.issues.length > 0;

  // Main upload interface
  return (
    <Card className="w-full max-w-2xl mx-auto max-h-[85vh] flex flex-col">
      <CardHeader className="pb-3 shrink-0">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <CardTitle className="text-base font-semibold">
              Upload School Verification Documents
            </CardTitle>

            {/* Child selector - only show if multiple children */}
            {allCases.length > 1 ? (
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Child:</span>
                <div className="relative">
                  <select
                    value={caseData?.case.case_id || ""}
                    onChange={handleChildChange}
                    className="appearance-none bg-muted text-sm font-medium pl-3 pr-8 py-1.5 rounded-md border-0 focus:ring-2 focus:ring-pink cursor-pointer"
                  >
                    {allCases.map((c) => (
                      <option key={c.case_id} value={c.case_id}>
                        {c.dependent_name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 size-4 text-muted-foreground pointer-events-none" />
                </div>
                <span className="text-xs text-muted-foreground">
                  • {caseData?.case.academic_year}
                </span>
              </div>
            ) : caseData ? (
              <p className="mt-1 text-xs text-muted-foreground">
                For {caseData.case.dependent_name} • {caseData.case.academic_year}
              </p>
            ) : null}
          </div>
          <Button variant="ghost" size="icon" onClick={handleClose}>
            <X className="size-4" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 overflow-y-auto flex-1">
        {/* Required documents checklist */}
        {caseData && caseData.case.required_documents.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Required Documents
              {allDocumentsReceived && (
                <span className="ml-2 text-green-600 normal-case">— All received</span>
              )}
            </p>
            <div className="grid grid-cols-2 gap-2">
              {caseData.case.required_documents.map((doc) => (
                <div
                  key={doc.kind}
                  className={`flex items-center gap-2 p-2 rounded-md text-xs ${
                    doc.received
                      ? "bg-green-500/10 text-green-700"
                      : "bg-muted text-muted-foreground"
                  }`}
                >
                  {doc.received ? (
                    <CheckCircle2 className="size-3.5 shrink-0" />
                  ) : (
                    <Clock className="size-3.5 shrink-0" />
                  )}
                  <span className="truncate">{doc.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Success message when all documents received (but not auto-approved) */}
        {allDocumentsReceived && !uploadResult && (
          <div className="flex items-start gap-2 p-3 rounded-lg border border-green-500/30 bg-green-500/5">
            <CheckCircle2 className="size-4 text-green-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-green-700">Everything we need is here</p>
              <p className="text-xs text-muted-foreground mt-1">
                All required documents have been received. You can close this window.
              </p>
            </div>
          </div>
        )}

        {/* Upload result with issues - show what needs to be fixed */}
        {uploadResult && uploadResult.status !== "success" && (
          <div className={`space-y-3 p-3 rounded-lg border ${
            hasIssues
              ? "border-amber-500/30 bg-amber-500/5"
              : "border-green-500/30 bg-green-500/5"
          }`}>
            <div className="flex items-start gap-2">
              {hasIssues ? (
                <AlertTriangle className="size-4 text-amber-500 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="size-4 text-green-500 mt-0.5 shrink-0" />
              )}
              <div>
                <p className={`text-sm font-medium ${hasIssues ? "text-amber-700" : "text-green-700"}`}>
                  {uploadResult.title}
                </p>
                <p className="text-xs text-muted-foreground mt-1">{uploadResult.message}</p>
              </div>
            </div>

            {uploadResult.issues.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium text-amber-700">Issues to fix:</p>
                <ul className="space-y-1 pl-4">
                  {uploadResult.issues.map((issue, i) => (
                    <li key={i} className="text-xs text-amber-700 list-disc">
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {uploadResult.missing_documents.length > 0 && (
              <div className="pt-2 border-t border-amber-500/20">
                <p className="text-xs font-medium text-amber-700">Still needed:</p>
                <div className="flex flex-wrap gap-1 mt-1">
                  {uploadResult.missing_documents.map((doc) => (
                    <Badge key={doc} variant="outline" className="text-[10px] border-amber-500/40">
                      {doc}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {uploadResult.can_reupload && uploadResult.reupload_message && (
              <p className="text-xs text-muted-foreground pt-2 border-t border-current/10">
                {uploadResult.reupload_message}
              </p>
            )}
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="flex items-start gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/5">
            <XCircle className="size-4 text-destructive mt-0.5 shrink-0" />
            <p className="text-xs text-destructive whitespace-pre-line">{error}</p>
          </div>
        )}

        {/* Drop zone - only show if documents are missing or there are issues to fix */}
        {(!allDocumentsReceived || hasIssues) && (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-muted-foreground/25 rounded-lg cursor-pointer hover:border-pink/50 hover:bg-pink/5 transition-colors"
          >
            <Upload className="size-8 text-muted-foreground/50" />
            <p className="mt-2 text-sm font-medium">
              {hasIssues ? "Upload corrected document(s)" : "Drop files here or click to browse"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">PDF, PNG, or JPEG up to 10MB each</p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        )}

        {/* Selected files */}
        {selectedFiles.length > 0 && (
          <div className="space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              Selected Files ({selectedFiles.length})
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
                  >
                    <X className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>

      {/* Fixed footer with action buttons */}
      <div className="shrink-0 p-4 pt-2 border-t bg-card space-y-2">
        <div className="flex gap-2">
          {allDocumentsReceived && !hasIssues ? (
            // All done - show single "Done" button
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700"
              onClick={() => {
                const childName = caseData?.case.dependent_name || "your child";
                onComplete?.(childName);
              }}
            >
              <CheckCircle2 className="size-4 mr-2" />
              Done
            </Button>
          ) : (
            // Still need uploads
            <>
              <Button variant="outline" className="flex-1" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                className="flex-1 bg-pink hover:bg-pink/90"
                disabled={selectedFiles.length === 0}
                onClick={handleUpload}
              >
                <Upload className="size-4 mr-2" />
                Upload {selectedFiles.length > 0 ? `(${selectedFiles.length})` : ""}
              </Button>
            </>
          )}
        </div>

        {/* Deadline reminder */}
        {caseData && !allDocumentsReceived && (
          <p className="text-[10px] text-center text-muted-foreground">
            Submission deadline: {caseData.case.submission_deadline}
          </p>
        )}
      </div>
    </Card>
  );
}
