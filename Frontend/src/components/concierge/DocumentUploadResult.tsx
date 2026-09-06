import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  FileCheck,
  FileX,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { UploadResponse, UploadStatus } from "@/lib/api/hcs11";

interface DocumentUploadResultProps {
  result: UploadResponse;
  onReupload?: () => void;
}

const STATUS_CONFIG: Record<
  UploadStatus,
  { icon: React.ElementType; color: string; bgColor: string; borderColor: string }
> = {
  success: {
    icon: CheckCircle2,
    color: "text-green-600",
    bgColor: "bg-green-500/10",
    borderColor: "border-green-500/30",
  },
  partial: {
    icon: Clock,
    color: "text-amber-600",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
  },
  needs_reupload: {
    icon: AlertTriangle,
    color: "text-amber-600",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
  },
  needs_review: {
    icon: Clock,
    color: "text-blue-600",
    bgColor: "bg-blue-500/10",
    borderColor: "border-blue-500/30",
  },
  incomplete: {
    icon: FileX,
    color: "text-amber-600",
    bgColor: "bg-amber-500/10",
    borderColor: "border-amber-500/30",
  },
  already_paid: {
    icon: FileCheck,
    color: "text-muted-foreground",
    bgColor: "bg-muted",
    borderColor: "border-muted-foreground/30",
  },
  error: {
    icon: XCircle,
    color: "text-destructive",
    bgColor: "bg-destructive/10",
    borderColor: "border-destructive/30",
  },
};

export function DocumentUploadResult({ result, onReupload }: DocumentUploadResultProps) {
  const config = STATUS_CONFIG[result.status] || STATUS_CONFIG.error;
  const Icon = config.icon;

  return (
    <div className={`rounded-lg border p-4 ${config.bgColor} ${config.borderColor}`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <Icon className={`size-5 shrink-0 mt-0.5 ${config.color}`} />
        <div className="min-w-0 flex-1">
          <p className={`font-semibold ${config.color}`}>{result.title}</p>
          <p className="mt-1 text-sm text-muted-foreground">{result.message}</p>
        </div>
      </div>

      {/* Document status grid */}
      {result.documents.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {result.documents.map((doc) => (
            <div
              key={doc.kind}
              className={`flex items-center gap-2 p-2 rounded-md text-xs ${
                doc.received && !doc.has_issues
                  ? "bg-green-500/10 text-green-700"
                  : doc.has_issues
                    ? "bg-amber-500/10 text-amber-700"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {doc.received && !doc.has_issues ? (
                <CheckCircle2 className="size-3.5 shrink-0" />
              ) : doc.has_issues ? (
                <AlertTriangle className="size-3.5 shrink-0" />
              ) : (
                <Clock className="size-3.5 shrink-0" />
              )}
              <span className="truncate">{doc.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Issues */}
      {result.issues.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs font-medium text-amber-700">Issues found:</p>
          <ul className="space-y-1 pl-4">
            {result.issues.map((issue, i) => (
              <li key={i} className="text-xs text-amber-700 list-disc">
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Missing documents */}
      {result.missing_documents.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-medium text-muted-foreground">Still needed:</p>
          <div className="flex flex-wrap gap-1 mt-1">
            {result.missing_documents.map((doc) => (
              <Badge
                key={doc}
                variant="outline"
                className="text-[10px] border-amber-500/40 bg-amber-500/5"
              >
                {doc}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Payment info */}
      {result.status === "success" && result.payment_amount && (
        <div className="mt-4 flex items-center justify-between p-3 rounded-md bg-green-500/10">
          <span className="text-sm font-medium text-green-700">Approved Amount</span>
          <span className="text-lg font-semibold text-green-700">
            AED {result.payment_amount.toLocaleString()}
          </span>
        </div>
      )}

      {/* Case reference */}
      {result.case_id && (
        <p className="mt-3 text-[10px] text-muted-foreground">Reference: {result.case_id}</p>
      )}

      {/* Reupload button */}
      {result.can_reupload && onReupload && (
        <Button
          variant="outline"
          size="sm"
          className="mt-4 w-full"
          onClick={onReupload}
        >
          Upload Missing Documents
        </Button>
      )}
    </div>
  );
}
