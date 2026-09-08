import { FileText, X } from "lucide-react";
import { Button } from "@/components/ui/button";

/** The files chosen but not yet sent, each removable before they go. */
export function PendingFiles({
  files,
  onRemove,
  busy,
}: {
  files: File[];
  onRemove: (index: number) => void;
  busy: boolean;
}) {
  if (files.length === 0) return null;

  return (
    <div className="mt-4 space-y-2">
      <p className="text-xs font-medium text-muted-foreground">
        {files.length} file{files.length === 1 ? "" : "s"} ready to send
      </p>
      {files.map((file, index) => (
        <div
          key={`${file.name}-${index}`}
          className="flex items-center gap-2 p-2 rounded-lg border bg-muted/30"
        >
          <FileText className="size-4 text-muted-foreground shrink-0" />
          <span className="text-sm truncate flex-1">{file.name}</span>
          <span className="text-xs text-muted-foreground shrink-0">
            {(file.size / 1024).toFixed(0)} KB
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="size-6 shrink-0"
            onClick={() => onRemove(index)}
            disabled={busy}
            aria-label={`Remove ${file.name}`}
          >
            <X className="size-3.5" />
          </Button>
        </div>
      ))}
    </div>
  );
}
