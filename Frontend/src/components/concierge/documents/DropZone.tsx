import { useRef } from "react";
import { Loader2, Upload } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { ACCEPTED_FILE_INPUT } from "./fileRules";

/**
 * Where files are dropped or chosen, and where progress is shown while they are read.
 *
 * Reading a document takes HCS-11 the better part of a minute, so this says so rather
 * than sitting still and looking broken.
 */
export function DropZone({
  onFiles,
  busy,
  stage,
  hint,
}: {
  onFiles: (files: File[]) => void;
  busy: boolean;
  stage?: string | null;
  hint: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">{hint}</p>

      <div
        onDrop={(e) => {
          e.preventDefault();
          if (busy) return;
          onFiles(Array.from(e.dataTransfer.files));
        }}
        onDragOver={(e) => e.preventDefault()}
        onClick={() => !busy && inputRef.current?.click()}
        className={`flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-lg transition-colors ${
          busy
            ? "border-muted-foreground/20 bg-muted/50 cursor-not-allowed"
            : "border-muted-foreground/25 cursor-pointer hover:border-pink/50 hover:bg-pink/5"
        }`}
      >
        {busy ? (
          <>
            <Loader2 className="size-8 text-pink animate-spin" />
            <p className="mt-2 text-sm font-medium">{stage || "Processing..."}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              This may take up to a minute while we check your documents
            </p>
            <Progress value={undefined} className="h-1 w-full max-w-xs mt-3" />
          </>
        ) : (
          <>
            <Upload className="size-8 text-muted-foreground/50" />
            <p className="mt-2 text-sm font-medium">Drop files here or click to browse</p>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FILE_INPUT}
          multiple
          onChange={(e) => {
            onFiles(Array.from(e.target.files ?? []));
            e.target.value = "";
          }}
          className="hidden"
          disabled={busy}
        />
      </div>
    </div>
  );
}
