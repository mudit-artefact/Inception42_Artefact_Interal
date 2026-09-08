import { useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileText,
  Loader2,
  Plane,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { useVisaDocumentUpload } from "@/hooks/useVisaDocumentUpload";
import { DropZone } from "./documents/DropZone";
import { PendingFiles } from "./documents/PendingFiles";
import { UploadError } from "./documents/UploadError";

/**
 * Sending employment visa documents in, for somebody who has not started yet.
 *
 * Three things this deliberately does not do, all because HCS-11 does not offer them:
 *
 * - No child selector. A new joiner has one case, for themself.
 * - No payment step. A visa case is never paid; it goes to the public relations officer.
 * - **No remove button.** HCS-11 keeps only the newest document of each kind and hides
 *   what it replaced, so a wrong document is corrected by sending the right one. Offering
 *   removal would be offering something that cannot happen.
 *
 * And one thing it does not need to do: work out which document a fault belongs to. The
 * server files each one against the row HCS-11 named, so a row shows HCS-11's own sentence.
 */

const STEPS = [
  { key: "documents", label: "Your documents", hint: "Everything your route needs" },
  { key: "lodging", label: "With the PRO", hint: "Lodged on your behalf" },
] as const;

function ProgressRail({
  caseStatus,
  received,
  total,
}: {
  caseStatus: string;
  received: number;
  total: number;
}) {
  const withThePro = caseStatus === "Ready for the PRO";

  return (
    <div className="w-48 shrink-0 border-l bg-muted/30 p-4 hidden md:block">
      <p className="text-xs font-semibold text-muted-foreground mb-4">Progress</p>
      <div className="space-y-4">
        {STEPS.map((step) => {
          const done = step.key === "documents" ? received === total && total > 0 : withThePro;
          const active = step.key === "documents" ? !done : done;
          return (
            <div key={step.key} className="flex items-start gap-2.5">
              {done ? (
                <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
              ) : (
                <Clock
                  className={`size-4 shrink-0 mt-0.5 ${
                    active ? "text-pink" : "text-muted-foreground/40"
                  }`}
                />
              )}
              <div className="min-w-0">
                <p className="text-xs font-medium leading-tight">{step.label}</p>
                <p className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                  {step.key === "documents" ? `${received} of ${total} received` : step.hint}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function VisaDocumentUpload({
  employeeId,
  onClose,
}: {
  employeeId: string;
  onClose: () => void;
}) {
  const {
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
  } = useVisaDocumentUpload();

  useEffect(() => {
    load(employeeId);
  }, [employeeId, load]);

  const busy = state === "uploading";

  if (state === "loading") {
    return (
      <Card className="w-full max-w-3xl mx-auto">
        <CardContent className="flex flex-col items-center justify-center py-16">
          <Loader2 className="size-8 text-pink animate-spin" />
          <p className="mt-3 text-sm text-muted-foreground">
            Looking up your visa case…
          </p>
        </CardContent>
      </Card>
    );
  }

  if (state === "no_case" || state === "error" || !caseData) {
    return (
      <Card className="w-full max-w-3xl mx-auto">
        <CardHeader className="flex flex-row items-start justify-between border-b">
          <h2 className="font-display text-lg font-semibold">Employment visa documents</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="size-4" />
          </Button>
        </CardHeader>
        <CardContent className="py-10 text-center">
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            {state === "no_case"
              ? "There is no employment visa case open for you. If you believe there should be, please contact People & Culture."
              : error ??
                "The visa service could not be reached, so I cannot show your case right now. Please try again shortly."}
          </p>
          <Button variant="outline" className="mt-5" onClick={() => load(employeeId)}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const rows = caseData.documents;
  const received = rows.filter((row) => row.received).length;
  const faulty = rows.filter((row) => row.has_issues);
  const everythingIn = received === rows.length && faulty.length === 0;

  return (
    <Card className="w-full max-w-3xl mx-auto max-h-[85vh] flex flex-col">
      <CardHeader className="shrink-0 border-b flex flex-row items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-display text-lg font-semibold flex items-center gap-2">
            <Plane className="size-4.5 text-pink" />
            Employment visa documents
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span>{caseData.case.employee_name}</span>
            {caseData.case.plan_name ? (
              <span className="truncate">{caseData.case.plan_name}</span>
            ) : null}
            {caseData.case.submission_deadline ? (
              <span>Due by {caseData.case.submission_deadline}</span>
            ) : null}
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
          <X className="size-4" />
        </Button>
      </CardHeader>

      <div className="flex flex-1 min-h-0">
        <CardContent className="flex-1 overflow-y-auto p-4">
          <div>
            <h3 className="text-sm font-semibold mb-1">What your route needs</h3>
            <p className="text-xs text-muted-foreground mb-3">
              {received} of {rows.length} received
            </p>

            <div className="space-y-2">
              {rows.map((row) => (
                <div
                  key={row.kind}
                  className={`flex items-start gap-2.5 p-2.5 rounded-lg border ${
                    row.has_issues ? "border-amber-500/40 bg-amber-500/5" : "bg-muted/20"
                  }`}
                >
                  {row.has_issues ? (
                    <AlertTriangle className="size-4 text-amber-600 shrink-0 mt-0.5" />
                  ) : row.received ? (
                    <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                  ) : (
                    <Clock className="size-4 text-muted-foreground/50 shrink-0 mt-0.5" />
                  )}

                  <div className="min-w-0 flex-1">
                    <p
                      className={`text-sm font-medium ${
                        row.has_issues
                          ? "text-amber-700 dark:text-amber-400"
                          : row.received
                            ? ""
                            : "text-muted-foreground"
                      }`}
                    >
                      {row.label}
                    </p>
                    {row.filename ? (
                      <p className="text-xs text-muted-foreground truncate flex items-center gap-1 mt-0.5">
                        <FileText className="size-3 shrink-0" />
                        {row.filename}
                      </p>
                    ) : null}
                    {/* HCS-11's own sentence, against the row HCS-11 named. */}
                    {row.issue_message ? (
                      <p className="text-xs text-amber-700 dark:text-amber-400 mt-1">
                        {row.issue_message}
                      </p>
                    ) : null}
                  </div>

                  {/* Replace, never remove: HCS-11 keeps the newest of each kind. */}
                  {row.has_issues ? (
                    <span className="text-[10px] font-medium text-amber-700 dark:text-amber-400 shrink-0 mt-1">
                      Send a corrected copy
                    </span>
                  ) : null}
                </div>
              ))}
            </div>
          </div>

          {everythingIn ? (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-lg border border-emerald-500/30 bg-emerald-500/10">
              <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
              <p className="text-sm">
                Everything we need is here. Your case has gone to the public relations
                officer — there is nothing further for you to do.
              </p>
            </div>
          ) : null}

          {result?.reupload_message && faulty.length > 0 ? (
            <div className="mt-4 p-3 rounded-lg border border-amber-500/30 bg-amber-500/10">
              <p className="text-sm">{result.reupload_message}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Sending it again replaces what is there — nothing needs removing first.
              </p>
            </div>
          ) : null}

          <UploadError message={error} />

          <div className="mt-4">
            <DropZone
              onFiles={addFiles}
              busy={busy}
              stage={stage}
              hint="PDF, JPG or PNG, up to 10 MB each. The order does not matter — each document is recognised from what is printed on it."
            />
          </div>

          <PendingFiles files={selectedFiles} onRemove={removeFile} busy={busy} />
        </CardContent>

        <ProgressRail
          caseStatus={caseData.case.case_status}
          received={received}
          total={rows.length}
        />
      </div>

      <div className="shrink-0 p-4 pt-3 border-t bg-card flex items-center justify-end gap-2">
        <Button
          variant="ghost"
          onClick={() => {
            reset();
            onClose();
          }}
          disabled={busy}
        >
          Close
        </Button>
        <Button onClick={upload} disabled={busy || selectedFiles.length === 0}>
          {busy ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Sending…
            </>
          ) : (
            `Send ${selectedFiles.length || ""} document${selectedFiles.length === 1 ? "" : "s"}`.trim()
          )}
        </Button>
      </div>
    </Card>
  );
}
