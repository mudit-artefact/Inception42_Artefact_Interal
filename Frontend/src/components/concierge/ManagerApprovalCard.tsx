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
          className="overflow-hidden rounded-xl border border-primary/20 bg-card shadow-xs"
        >
          <div className="flex items-center justify-between border-b border-border/50 bg-primary/5 px-3.5 py-2">
            <div className="flex items-center gap-2">
              <span className="grid size-6 place-items-center rounded-md bg-primary/15 text-primary">
                <Clock className="size-3.5" />
              </span>
              <span className="font-display text-xs font-semibold text-foreground">
                Pending Approval
              </span>
            </div>
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
                  {item.days_requested} {item.days_requested === 1 ? "day" : "days"}
                </span>
              </div>
            </div>

            <div className="rounded-lg bg-muted/40 p-2 text-xs flex items-center gap-2 border border-border/40">
              <Calendar className="size-3.5 text-muted-foreground shrink-0" />
              <span className="font-medium text-foreground">
                {item.start_date} → {item.end_date}
              </span>
            </div>

            <div className="flex items-center gap-2 pt-1 border-t border-border/40">
              <Button
                size="sm"
                onClick={() => onAction(`Approve leave #${item.request_id}`)}
                className="h-8 gap-1.5 px-3.5 text-xs bg-primary hover:bg-primary/90 text-primary-foreground font-medium shadow-xs"
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
