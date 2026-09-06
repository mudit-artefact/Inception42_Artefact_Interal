import { useCallback, useEffect, useRef, useState } from "react";
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

  const [forceShowUpload, setForceShowUpload] = useState(false);

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
    setForceShowUpload(false);
    onClose();
  };

  const handleChildChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const caseId = e.target.value;
    if (caseId) {
      setForceShowUpload(false);
      selectCase(caseId);
    }
  };

  // Check if all required documents are received (avoiding [].every which is vacuously true)
  const hasRequiredDocs = (caseData?.case.required_documents.length ?? 0) > 0;
  const allDocumentsReceived = hasRequiredDocs
    ? (caseData?.case.required_documents.every((doc) => doc.received) ?? false)
    : caseData?.case.case_status === "Approved";

  // Loading state
  if (status === "loading_cases") {
    return (
      <Card className="w-full max-w-2xl mx-auto bg-white dark:bg-zinc-900 text-foreground border border-border shadow-2xl rounded-2xl">
        <CardContent className="flex flex-col items-center justify-center py-12">
          <Loader2 className="size-8 animate-spin text-pink" />
          <p className="mt-3 text-sm font-medium text-slate-600 dark:text-slate-300">Loading your verification cases...</p>
        </CardContent>
      </Card>
    );
  }

  // No case found
  if (status === "no_case") {
    return (
      <Card className="w-full max-w-2xl mx-auto bg-white dark:bg-zinc-900 text-foreground border border-border shadow-2xl rounded-2xl">
        <CardHeader className="pb-3 border-b border-border">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base font-semibold">Document Verification</CardTitle>
            <Button variant="ghost" size="icon" onClick={handleClose}>
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col items-center justify-center py-8">
          <AlertTriangle className="size-10 text-amber-500" />
          <p className="mt-3 text-sm text-center text-slate-600 dark:text-slate-300">
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

    return (
      <Card className="w-full max-w-2xl mx-auto bg-white dark:bg-zinc-900 border border-emerald-500/40 shadow-2xl rounded-2xl overflow-hidden">
        <div className="bg-emerald-50 dark:bg-emerald-950/50 border-b border-emerald-500/20 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-5" />
            </div>
            <div>
              <CardTitle className="text-base font-bold text-emerald-950 dark:text-emerald-200">
                {uploadResult.title}
              </CardTitle>
              <p className="text-xs text-emerald-800 dark:text-emerald-300 font-medium">
                Document verification completed
              </p>
            </div>
          </div>
          <Button variant="ghost" size="icon" className="text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100" onClick={handleClose}>
            <X className="size-4" />
          </Button>
        </div>
        <CardContent className="p-6 space-y-5">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100 leading-relaxed">
            {uploadResult.message}
          </p>

          {uploadResult.payment_amount && (
            <div className="flex items-center justify-between p-4 rounded-xl bg-emerald-50/80 dark:bg-emerald-950/40 border border-emerald-300/60 dark:border-emerald-800/60 shadow-xs">
              <span className="text-sm font-semibold text-emerald-950 dark:text-emerald-200">Approved Amount</span>
              <span className="text-xl font-extrabold text-emerald-700 dark:text-emerald-300">
                AED {uploadResult.payment_amount.toLocaleString()}
              </span>
            </div>
          )}

          {uploadResult.case_id && (
            <p className="text-xs text-slate-500 dark:text-slate-400 font-medium">
              Reference: <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">{uploadResult.case_id}</span>
            </p>
          )}

          <Button className="w-full h-10 font-semibold bg-pink hover:bg-pink/90 text-white rounded-xl shadow-md cursor-pointer transition-all" onClick={() => { onComplete?.(childName); }}>
            Done
          </Button>
        </CardContent>
      </Card>
    );
  }

  // Uploading state
  if (status === "uploading") {
    return (
      <Card className="w-full max-w-2xl mx-auto bg-white dark:bg-zinc-900 text-foreground border border-border shadow-2xl rounded-2xl overflow-hidden">
        <CardHeader className="pb-3 border-b border-border">
          <CardTitle className="text-base font-semibold">Uploading & Verifying Documents</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 py-8">
          <div className="flex flex-col items-center py-4">
            <Loader2 className="size-10 animate-spin text-pink" />
            <p className="mt-4 text-sm font-semibold text-foreground">{stage || "Processing..."}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Securely validating submitted documents against education allowance criteria
            </p>
          </div>
          <Progress value={undefined} className="h-1.5" />
        </CardContent>
      </Card>
    );
  }

  // Count how many documents still need to be uploaded
  const missingCount = caseData?.case.required_documents.filter((doc) => !doc.received).length ?? 0;
  const hasIssues = uploadResult && uploadResult.issues.length > 0;

  // Main upload interface
  return (
    <Card className="w-full max-w-2xl mx-auto max-h-[85vh] flex flex-col bg-white dark:bg-zinc-900 text-foreground border border-border shadow-2xl rounded-2xl overflow-hidden">
      <CardHeader className="pb-3 shrink-0 border-b border-border bg-slate-50/50 dark:bg-zinc-900/50">
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
                  className={`flex items-center gap-2 p-2.5 rounded-lg text-xs font-medium ${
                    doc.received
                      ? "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/40"
                      : "bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-slate-400 border border-slate-200/60 dark:border-zinc-700/60"
                  }`}
                >
                  {doc.received ? (
                    <CheckCircle2 className="size-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : (
                    <Clock className="size-3.5 shrink-0 text-slate-400" />
                  )}
                  <span className="truncate">{doc.label}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Success message when all documents received (but not auto-approved) */}
        {allDocumentsReceived && !uploadResult && (
          <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-50/70 dark:bg-emerald-950/30 space-y-2.5">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-bold text-emerald-950 dark:text-emerald-200">
                  {caseData?.case.case_status === "Approved"
                    ? "Approved for Education Allowance"
                    : "Everything we need is here"}
                </p>
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mt-0.5">
                  {caseData?.case.approved_amount_aed
                    ? `AED ${caseData.case.approved_amount_aed.toLocaleString()} ready for payroll processing.`
                    : "All required documents have been received for this academic cycle."}
                </p>
              </div>
            </div>
            {!forceShowUpload && selectedFiles.length === 0 && (
              <div className="pt-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs gap-1.5 border-pink/30 text-pink hover:bg-pink/10 cursor-pointer font-semibold"
                  onClick={() => setForceShowUpload(true)}
                >
                  <Upload className="size-3.5" />
                  Upload Replacement or New Document
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Upload result with issues - show what needs to be fixed */}
        {uploadResult && uploadResult.status !== "success" && (
          <div className={`space-y-3 p-4 rounded-xl border ${
            hasIssues
              ? "border-amber-500/40 bg-amber-50/80 dark:bg-amber-950/40"
              : "border-emerald-500/40 bg-emerald-50/80 dark:bg-emerald-950/40"
          }`}>
            <div className="flex items-start gap-3">
              {hasIssues ? (
                <AlertTriangle className="size-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="size-5 text-emerald-600 dark:text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div>
                <p className={`text-sm font-bold ${hasIssues ? "text-amber-950 dark:text-amber-200" : "text-emerald-950 dark:text-emerald-200"}`}>
                  {uploadResult.title}
                </p>
                <p className="text-xs font-medium text-slate-700 dark:text-slate-300 mt-1">{uploadResult.message}</p>
              </div>
            </div>

            {uploadResult.issues.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <p className="text-xs font-bold text-amber-900 dark:text-amber-200">Issues to fix:</p>
                <ul className="space-y-1 pl-4">
                  {uploadResult.issues.map((issue, i) => (
                    <li key={i} className="text-xs font-medium text-amber-900 dark:text-amber-300 list-disc">
                      {issue}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {uploadResult.missing_documents.length > 0 && (
              <div className="pt-2 border-t border-amber-500/20">
                <p className="text-xs font-bold text-amber-900 dark:text-amber-200">Still needed:</p>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {uploadResult.missing_documents.map((doc) => (
                    <Badge key={doc} variant="outline" className="text-[11px] font-semibold border-amber-500/50 bg-amber-100/50 text-amber-900 dark:text-amber-200">
                      {doc}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {uploadResult.can_reupload && uploadResult.reupload_message && (
              <p className="text-xs font-medium text-slate-600 dark:text-slate-400 pt-2 border-t border-current/10">
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

        {/* Drop zone - show if documents are missing, has issues, user requested upload, or files are selected */}
        {(!allDocumentsReceived || hasIssues || forceShowUpload || selectedFiles.length > 0) && (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onClick={() => fileInputRef.current?.click()}
            className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-pink/30 hover:border-pink bg-pink/5 hover:bg-pink/10 rounded-lg cursor-pointer transition-colors"
          >
            <Upload className="size-8 text-pink/70" />
            <p className="mt-2 text-sm font-medium text-foreground">
              {hasIssues
                ? "Upload corrected document(s)"
                : allDocumentsReceived
                ? "Drop new or replacement document here"
                : "Drop official school certificate here or click to browse"}
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
          {allDocumentsReceived && !hasIssues && !forceShowUpload && selectedFiles.length === 0 ? (
            // All done - show "Upload Document" and "Done"
            <>
              <Button
                variant="outline"
                className="flex-1 border-pink/30 text-pink hover:bg-pink/10 cursor-pointer"
                onClick={() => setForceShowUpload(true)}
              >
                <Upload className="size-4 mr-2" />
                Upload Document
              </Button>
              <Button
                className="flex-1 bg-green-600 hover:bg-green-700 text-white cursor-pointer"
                onClick={() => {
                  const childName = caseData?.case.dependent_name || "your child";
                  onComplete?.(childName);
                }}
              >
                <CheckCircle2 className="size-4 mr-2" />
                Done
              </Button>
            </>
          ) : (
            // Needs upload or has selected files
            <>
              <Button variant="outline" className="flex-1 cursor-pointer" onClick={handleClose}>
                Cancel
              </Button>
              <Button
                className="flex-1 bg-pink hover:bg-pink/90 text-white font-medium cursor-pointer"
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
