import { AlertTriangle } from "lucide-react";

/** Whatever went wrong, said once and plainly. */
export function UploadError({ message }: { message?: string | null }) {
  if (!message) return null;

  return (
    <div className="mt-4 flex items-start gap-2 p-3 rounded-lg border border-destructive/30 bg-destructive/10">
      <AlertTriangle className="size-4 text-destructive shrink-0 mt-0.5" />
      <p className="text-sm text-destructive">{message}</p>
    </div>
  );
}
