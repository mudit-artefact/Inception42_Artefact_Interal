import {
  CalendarDays,
  GraduationCap,
  PlaneTakeoff,
  type LucideIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";
import type { RequestRow, Tone } from "@/lib/requests";

const ICON: Record<RequestRow["type"], LucideIcon> = {
  Leave: CalendarDays,
  "Kids schooling": GraduationCap,
  "Employment visa": PlaneTakeoff,
};

const TYPE_STYLE: Record<RequestRow["type"], string> = {
  Leave: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  "Kids schooling": "bg-pink-500/10 text-pink-700 dark:text-pink-400",
  "Employment visa": "bg-amber-500/10 text-amber-700 dark:text-amber-400",
};

const DOT: Record<Tone, string> = {
  done: "bg-emerald-500",
  attention: "bg-amber-500",
  progress: "bg-sky-500",
  waiting: "bg-muted-foreground/40",
};

interface RequestsTableProps {
  rows: RequestRow[];
  className?: string;
}

export function RequestsTable({ rows, className }: RequestsTableProps) {
  if (rows.length === 0) {
    return (
      <p className={cn("px-4 py-8 text-center text-sm text-muted-foreground", className)}>
        You have not made any requests yet.
      </p>
    );
  }

  return (
    <div className={cn("overflow-x-auto", className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs uppercase tracking-wide">Request</TableHead>
            <TableHead className="text-xs uppercase tracking-wide">Type</TableHead>
            <TableHead className="text-xs uppercase tracking-wide">Date submitted</TableHead>
            <TableHead className="text-xs uppercase tracking-wide">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const Icon = ICON[row.type];
            return (
              <TableRow key={row.key}>
                <TableCell>
                  <div className="flex items-start gap-3">
                    <Icon
                      className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground">{row.title}</p>
                      {row.detail && (
                        <p className="truncate text-xs text-muted-foreground">{row.detail}</p>
                      )}
                    </div>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge
                    variant="secondary"
                    className={cn("font-normal", TYPE_STYLE[row.type])}
                  >
                    {row.type}
                  </Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {/* Blank rather than invented. A request that has not been submitted has
                      no submission date, and seeded rows carry the moment the database was
                      written rather than a real one. */}
                  {row.submitted || "—"}
                </TableCell>
                <TableCell>
                  {/* The word the owning system uses, not one made up here. */}
                  <span className="inline-flex items-center gap-2 text-sm">
                    <span
                      className={cn("size-2 shrink-0 rounded-full", DOT[row.tone])}
                      aria-hidden="true"
                    />
                    {row.status}
                  </span>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
