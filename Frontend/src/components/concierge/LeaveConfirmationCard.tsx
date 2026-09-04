import React from "react";
import { Calendar, CheckCircle2, AlertCircle, Clock, UserCheck, ArrowRight, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { ActionPayload } from "@/lib/api/types";

interface LeaveConfirmationCardProps {
  payload: ActionPayload;
  onConfirm?: ((text: string) => void) | undefined;
  isLatestAssistantMessage?: boolean | undefined;
}

export function LeaveConfirmationCard({
  payload,
  onConfirm,
  isLatestAssistantMessage = true,
}: LeaveConfirmationCardProps) {
  if (!payload || !payload.action_type) return null;

  const {
    action_type,
    leave_type,
    start_date,
    end_date,
    working_days,
    balance_before,
    balance_after,
    approver_name,
    notice_compliant,
    requires_medical_certificate,
    receipt,
    violations,
  } = payload;

  // 1. Pending Approval or Success confirmation card
  if ((action_type === "LEAVE_SUBMITTED_PENDING_APPROVAL" || action_type === "LEAVE_SUBMITTED_SUCCESS") && receipt) {
    const isPending = receipt.status === "Pending" || action_type === "LEAVE_SUBMITTED_PENDING_APPROVAL";
    return (
      <div className={`mt-3 overflow-hidden rounded-xl border p-4 text-sm shadow-sm transition-all ${
        isPending
          ? "border-amber-500/30 bg-amber-500/5 dark:border-amber-500/20 dark:bg-amber-950/20"
          : "border-emerald-500/30 bg-emerald-500/5 dark:border-emerald-500/20 dark:bg-emerald-950/20"
      }`}>
        <div className={`flex items-center gap-2 font-medium ${isPending ? "text-amber-600 dark:text-amber-400" : "text-emerald-600 dark:text-emerald-400"}`}>
          {isPending ? <Clock className="size-5 shrink-0 text-amber-500" /> : <CheckCircle2 className="size-5 shrink-0 text-emerald-500" />}
          <span className="font-semibold">Leave Request #{receipt.request_id} Logged</span>
          <Badge variant="outline" className={`ml-auto text-[10px] ${
            isPending
              ? "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400"
              : "border-emerald-500/40 bg-emerald-500/10 text-emerald-600"
          }`}>
            {receipt.status || (isPending ? "Pending Approval" : "Approved")}
          </Badge>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-background/60 p-2.5 border border-border/50">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Period</span>
            <span className="font-medium text-foreground">{receipt.start_date} → {receipt.end_date}</span>
            <span className="text-primary font-semibold text-[11px] block mt-0.5">{receipt.days_requested} Working Days</span>
          </div>
          <div className="rounded-lg bg-background/60 p-2.5 border border-border/50">
            <span className="text-muted-foreground block text-[10px] uppercase font-semibold">Balance</span>
            <span className="font-medium text-foreground">{receipt.current_balance ?? receipt.remaining_balance} Days Available</span>
            <span className="text-muted-foreground text-[10px] block mt-0.5">{isPending ? "Will debit upon approval" : "Updated balance"}</span>
          </div>
        </div>

        <div className="mt-2.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          <UserCheck className="size-3.5 text-primary" />
          <span>Forwarded to Line Manager: <strong className="text-foreground">{receipt.approver_name}</strong> for review</span>
        </div>
      </div>
    );
  }


  // 2. Policy violation card
  if (action_type === "POLICY_VIOLATION") {
    return (
      <div className="mt-3 overflow-hidden rounded-xl border border-rose-500/30 bg-rose-500/5 p-4 text-sm shadow-sm dark:border-rose-500/20 dark:bg-rose-950/20">
        <div className="flex items-center gap-2 font-medium text-rose-600 dark:text-rose-400">
          <AlertCircle className="size-5 shrink-0 text-rose-500" />
          <span className="font-semibold">Policy Compliance Check Failed</span>
        </div>
        {violations && violations.length > 0 ? (
          <ul className="mt-2.5 space-y-1.5 text-xs text-rose-600/90 dark:text-rose-300">
            {violations.map((v: string, idx: number) => (
              <li key={idx} className="flex items-start gap-1.5">
                <span className="text-rose-500 mt-0.5">•</span>
                <span>{v}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  // 3. Human-in-the-Loop Confirmation Card
  if (action_type === "CONFIRM_LEAVE_APPLICATION") {
    return (
      <div className="mt-3 overflow-hidden rounded-xl border border-pink/30 bg-gradient-to-b from-pink/5 to-transparent p-4 text-sm shadow-sm transition-all">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/50 pb-2.5">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-pink/10 text-pink">
              <Calendar className="size-4" />
            </div>
            <div>
              <span className="font-semibold text-foreground text-xs">{leave_type} Application</span>
              <span className="block text-[10px] text-muted-foreground">Deterministic Pre-Flight Verified</span>
            </div>
          </div>
          <Badge variant="outline" className="border-pink/40 bg-pink/10 text-pink text-[10px]">
            Confirmation Required
          </Badge>
        </div>

        {/* Date Details */}
        <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-background/80 p-2.5 border border-border/50 shadow-2xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Dates</span>
            <div className="font-medium text-foreground mt-0.5 flex items-center gap-1">
              <span>{start_date}</span>
              <ArrowRight className="size-3 text-muted-foreground" />
              <span>{end_date}</span>
            </div>
          </div>

          <div className="rounded-lg bg-background/80 p-2.5 border border-border/50 shadow-2xs">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Working Days</span>
            <div className="font-medium text-foreground mt-0.5 flex items-center gap-1.5">
              <Clock className="size-3.5 text-pink" />
              <span>{working_days} Days Deducted</span>
            </div>
          </div>
        </div>

        {/* Balance & Manager Impact */}
        <div className="mt-2.5 rounded-lg bg-muted/40 p-2.5 text-xs space-y-1.5 border border-border/40">
          <div className="flex items-center justify-between text-muted-foreground">
            <span>Current Balance:</span>
            <span className="font-semibold text-foreground">{balance_before} Days</span>
          </div>
          <div className="flex items-center justify-between text-muted-foreground">
            <span>Projected Balance:</span>
            <span className="font-semibold text-emerald-600 dark:text-emerald-400">{balance_after} Days</span>
          </div>
          <div className="flex items-center justify-between pt-1 border-t border-border/40 text-muted-foreground">
            <span>Routing to Line Manager:</span>
            <span className="font-medium text-foreground">{approver_name}</span>
          </div>
          {notice_compliant ? (
            <div className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400 pt-0.5">
              <CheckCircle2 className="size-3" />
              <span>Notice period compliant (HC-PC-001 §1.4)</span>
            </div>
          ) : null}
          {requires_medical_certificate ? (
            <div className="flex items-center gap-1 text-[11px] text-amber-600 dark:text-amber-400 pt-0.5">
              <AlertCircle className="size-3" />
              <span>Medical certificate required (&gt;2 days sick leave)</span>
            </div>
          ) : null}
        </div>

        {/* Action Buttons */}
        {isLatestAssistantMessage && onConfirm ? (
          <div className="mt-3.5 flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => onConfirm("Confirm")}
              className="flex-1 bg-pink text-white hover:bg-pink/90 text-xs font-medium h-8 shadow-xs"
            >
              <CheckCircle2 className="size-3.5 mr-1.5" />
              Confirm & Submit
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onConfirm("Cancel")}
              className="text-xs h-8 text-muted-foreground hover:text-foreground hover:bg-muted"
            >
              <XCircle className="size-3.5 mr-1" />
              Cancel
            </Button>
          </div>
        ) : null}
      </div>
    );
  }

  return null;
}
