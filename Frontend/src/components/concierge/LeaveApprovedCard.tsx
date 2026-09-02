import { CalendarCheck, Mail, Download, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface LeaveApprovedCardProps {
  approvedLeave: {
    request_id: number;
    leave_type: string;
    start_date: string;
    end_date: string;
    days_requested: number;
    approver_name: string;
    employee_name?: string;
    manager_email?: string;
  };
}

export function LeaveApprovedCard({ approvedLeave }: LeaveApprovedCardProps) {
  const {
    request_id,
    leave_type,
    start_date,
    end_date,
    days_requested,
    approver_name,
    employee_name = "Employee",
    manager_email = "fatima.qubaisi@hcservices.ae",
  } = approvedLeave;

  // 1. Download .ics iCalendar event
  const downloadIcs = () => {
    const startFormatted = start_date.replace(/-/g, "");
    // In iCal, end date for all-day events is exclusive, so add 1 day or use exact date
    const endFormatted = end_date.replace(/-/g, "");

    const icsData = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Health Corporate Services//Leave Concierge//EN",
      "CALSCALE:GREGORIAN",
      "METHOD:PUBLISH",
      "BEGIN:VEVENT",
      `UID:leave-${request_id}@hcservices.ae`,
      `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").split(".")[0]}Z`,
      `DTSTART;VALUE=DATE:${startFormatted}`,
      `DTEND;VALUE=DATE:${endFormatted}`,
      `SUMMARY:${leave_type} - ${employee_name}`,
      `DESCRIPTION:Approved ${leave_type} (${days_requested} working days) approved by ${approver_name}.\\nRequest ID: #${request_id}`,
      "STATUS:CONFIRMED",
      "TRANSP:OPAQUE",
      "END:VEVENT",
      "END:VCALENDAR",
    ].join("\r\n");

    const blob = new Blob([icsData], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `leave-request-${request_id}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 2. Open pre-composed mailto
  const getMailtoUrl = () => {
    const subject = encodeURIComponent(`Approved Leave Notification: ${employee_name} (${start_date} to ${end_date})`);
    const body = encodeURIComponent(
      `Dear ${approver_name} and HR Operations Team,\n\n` +
      `This is to confirm that my ${leave_type} request (#${request_id}) for ${days_requested} working days ` +
      `(from ${start_date} to ${end_date}) has been approved.\n\n` +
      `I have updated my calendar and out-of-office status accordingly.\n\n` +
      `Best regards,\n` +
      `${employee_name}\n` +
      `Health Corporate Services (HCS)`
    );
    return `mailto:${manager_email}?cc=hr@hcservices.ae,people@hcservices.ae&subject=${subject}&body=${body}`;
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-emerald-500/30 bg-emerald-50/60 dark:bg-emerald-950/20 shadow-sm">
      <div className="flex items-center gap-2 border-b border-emerald-500/20 bg-emerald-100/50 dark:bg-emerald-900/30 px-3.5 py-2">
        <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
        <span className="font-display text-xs font-semibold text-emerald-900 dark:text-emerald-200">
          Leave Request #{request_id} Approved
        </span>
      </div>

      <div className="p-3.5 space-y-3">
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-lg bg-background/80 p-2 border border-border/40">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Period</span>
            <span className="font-medium text-foreground">{start_date} → {end_date}</span>
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold block mt-0.5">
              {days_requested} working days
            </span>
          </div>

          <div className="rounded-lg bg-background/80 p-2 border border-border/40">
            <span className="text-[10px] uppercase font-semibold text-muted-foreground block">Approved By</span>
            <span className="font-medium text-foreground">{approver_name}</span>
            <span className="text-[11px] text-muted-foreground block mt-0.5">Line Manager</span>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Would you like to mark this on your calendar or send a formal notification email to your manager and HR?
        </p>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button
            size="sm"
            variant="outline"
            onClick={downloadIcs}
            className="h-8 gap-1.5 text-xs border-emerald-600/30 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-100/50 dark:hover:bg-emerald-900/30"
          >
            <Download className="size-3.5" />
            Add to Calendar (.ics)
          </Button>

          <a href={getMailtoUrl()} target="_blank" rel="noopener noreferrer">
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5 text-xs border-border hover:bg-muted"
            >
              <Mail className="size-3.5" />
              Email Manager & HR
            </Button>
          </a>
        </div>
      </div>
    </div>
  );
}
