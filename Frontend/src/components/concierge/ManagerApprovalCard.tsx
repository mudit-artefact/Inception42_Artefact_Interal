import { CheckCircle2, XCircle, Clock, UserCheck, Calendar } from "lucide-react";
import { Button } from "@/components/ui/button";

interface PendingApproval {
  request_id: number;
  employee_id: string;
  employee_name: string;
  employee_role?: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  notes?: string;
  created_at?: string;
}

interface ManagerApprovalCardProps {
  pendingApprovals: PendingApproval[];
  onAction: (actionText: string) => void;
}

export function ManagerApprovalCard({ pendingApprovals, onAction }: ManagerApprovalCardProps) {
  if (!pendingApprovals || pendingApprovals.length === 0) return null;

  return (
    <div className="mt-3 space-y-3">
      {pendingApprovals.map((item) => (
        <div
          key={item.request_id}
          className="overflow-hidden rounded-xl border border-primary/25 bg-card/90 shadow-sm"
        >
          <div className="flex items-center justify-between border-b border-border/60 bg-muted/40 px-3.5 py-2">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
                <Clock className="size-3.5" />
              </span>
              <span className="font-display text-xs font-semibold text-foreground">
                Pending Approval · Request #{item.request_id}
              </span>
            </div>
            <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
              Needs Your Review
            </span>
          </div>

          <div className="p-3.5 space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <span className="font-display text-sm font-semibold text-foreground block">
                  {item.employee_name}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  {item.employee_role || item.employee_id} · {item.leave_type}
                </span>
              </div>
              <div className="text-right">
                <span className="font-display text-sm font-semibold text-primary">
                  {item.days_requested} days
                </span>
                <span className="text-[11px] text-muted-foreground block">working duration</span>
              </div>
            </div>

            <div className="rounded-lg bg-muted/40 p-2 text-xs flex items-center gap-2">
              <Calendar className="size-3.5 text-muted-foreground shrink-0" />
              <span className="font-medium text-foreground">
                {item.start_date} → {item.end_date}
              </span>
            </div>

            {item.notes && (
              <p className="text-xs text-muted-foreground italic">
                "{item.notes}"
              </p>
            )}

            <div className="flex items-center gap-2 pt-1 border-t border-border/40">
              <Button
                size="sm"
                onClick={() => onAction(`Approve leave #${item.request_id}`)}
                className="h-8 gap-1.5 px-3.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
              >
                <CheckCircle2 className="size-3.5" />
                Approve Leave
              </Button>

              <Button
                size="sm"
                variant="outline"
                onClick={() => onAction(`Reject leave #${item.request_id}`)}
                className="h-8 gap-1.5 px-3.5 text-xs text-destructive hover:bg-destructive/10 border-destructive/30"
              >
                <XCircle className="size-3.5" />
                Reject
              </Button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
