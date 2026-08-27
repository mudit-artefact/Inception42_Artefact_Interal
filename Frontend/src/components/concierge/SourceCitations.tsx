import { useState } from "react";
import { BookOpen, ChevronDown, ChevronUp, Database, ExternalLink, FileText, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { API_BASE_URL } from "@/lib/api/config";
import type { PolicySource } from "@/lib/api/types";

function resolveMediaUrl(path?: string): string {
  if (!path) return "#";
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = API_BASE_URL || "http://localhost:8000";
  return `${base}${path.startsWith("/") ? "" : "/"}${path}`;
}

export function SourceCitations({ sources }: { sources: PolicySource[] }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!sources || sources.length === 0) return null;

  const dbSources = sources.filter((s) => s.source_type === "database");
  const policySources = sources.filter((s) => s.source_type !== "database");
  const hasVisualDiagrams = policySources.some((s) => s.has_image);

  return (
    <div className="mt-3 overflow-hidden rounded-lg border bg-muted/30 transition-all">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-xs transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={isOpen}
      >
        <span className="flex flex-wrap items-center gap-1.5">
          <BookOpen aria-hidden="true" className="size-3.5 text-pink" />
          <span className="font-semibold uppercase tracking-wider text-muted-foreground text-[11px]">
            Verified Sources ({sources.length})
          </span>
          <Badge variant="secondary" className="px-1.5 py-0 text-[10px] font-normal text-muted-foreground">
            {isOpen ? "Click to hide" : "Click to view"}
          </Badge>
          {dbSources.length > 0 ? (
            <Badge variant="outline" className="items-center gap-1 border-blue-500/30 bg-blue-500/5 text-[10px] text-blue-600 dark:text-blue-400">
              <Database className="size-2.5" />
              <span>SQL Database</span>
            </Badge>
          ) : null}
          {policySources.length > 0 ? (
            <Badge variant="outline" className="items-center gap-1 border-purple-500/30 bg-purple-500/5 text-[10px] text-purple-600 dark:text-purple-400">
              <FileText className="size-2.5" />
              <span>Policy PDFs ({policySources.length})</span>
            </Badge>
          ) : null}
          {hasVisualDiagrams ? (
            <Badge variant="outline" className="hidden sm:inline-flex items-center gap-1 border-pink/30 bg-pink/5 text-[10px] text-pink">
              <Sparkles className="size-2.5" />
              PDF Flowcharts
            </Badge>
          ) : null}
        </span>
        {isOpen ? (
          <ChevronUp aria-hidden="true" className="size-4 text-muted-foreground" />
        ) : (
          <ChevronDown aria-hidden="true" className="size-4 text-muted-foreground" />
        )}
      </button>

      {isOpen ? (
        <div className="border-t bg-muted/10 p-3">
          <ol className="space-y-2">
            {sources.map((source, i) => {
              const isDatabase = source.source_type === "database";
              const basePdfHref = resolveMediaUrl(source.pdf_url || source.url);
              const pageNum = source.page_number;
              const pdfPageHref = pageNum ? `${basePdfHref}#page=${pageNum}` : basePdfHref;

              return (
                <li key={source.id ?? `${source.title}-${i}`} className="flex items-center gap-2 text-xs py-0.5">
                  <span
                    aria-hidden="true"
                    className={`grid size-4 shrink-0 place-items-center rounded text-[10px] font-semibold ${
                      isDatabase ? "bg-blue-500/10 text-blue-600 dark:text-blue-400" : "bg-pink/10 text-pink"
                    }`}
                  >
                    {i + 1}
                  </span>

                  <div className="min-w-0 flex-1 flex flex-wrap items-center gap-1.5">
                    {isDatabase ? (
                      <>
                        <span className="font-medium text-foreground inline-flex items-center gap-1">
                          <Database className="size-3 text-blue-500" />
                          {source.title}
                        </span>
                        <Badge variant="secondary" className="border-blue-500/20 bg-blue-500/10 text-[10px] text-blue-700 dark:text-blue-300">
                          Live SQL Record
                        </Badge>
                        {source.table_name ? (
                          <Badge variant="outline" className="text-[10px] font-mono text-muted-foreground">
                            Tables: {source.table_name}
                          </Badge>
                        ) : null}
                      </>
                    ) : (
                      <>
                        <a
                          href={pdfPageHref}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-foreground hover:text-pink hover:underline inline-flex items-center gap-1"
                        >
                          <FileText className="size-3 text-pink" />
                          {source.title || source.source || "Policy Document"}
                        </a>

                        {source.section ? (
                          <Badge variant="outline" className="font-normal text-[11px]">
                            {source.section}
                          </Badge>
                        ) : null}

                        {source.has_image ? (
                          <Badge variant="secondary" className="gap-1 border-pink/20 bg-pink/10 text-[10px] font-normal text-pink">
                            <Sparkles className="size-2.5" />
                            <span>PDF Flowchart {pageNum ? `(Page ${pageNum})` : ""}</span>
                          </Badge>
                        ) : null}

                        {source.score ? (
                          <Badge variant="secondary" className="text-[10px] font-normal text-muted-foreground">
                            {Math.round(source.score * 100)}% match
                          </Badge>
                        ) : null}

                        {source.pdf_url ? (
                          <a
                            href={pdfPageHref}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] text-muted-foreground underline-offset-2 hover:text-foreground hover:underline ml-auto"
                          >
                            <span>View PDF {pageNum ? `(Page ${pageNum})` : ""}</span>
                            <ExternalLink className="size-2.5" />
                          </a>
                        ) : null}
                      </>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        </div>
      ) : null}
    </div>
  );
}
