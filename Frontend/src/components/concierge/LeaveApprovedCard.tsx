import { Calendar, Mail, Download, CheckCircle2, ExternalLink } from "lucide-react";
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

  // 1. Direct Microsoft Teams / Outlook 365 Web Calendar Compose Link
  const openTeamsCalendar = () => {
    const timeText = start_date === end_date ? `on ${start_date}` : `from ${start_date} to ${end_date}`;
    const title = encodeURIComponent(`${leave_type} (Out of Office)`);
    const managerContact = manager_email ? `${approver_name} (${manager_email})` : approver_name;
    const body = encodeURIComponent(
      `I will be on leave ${timeText}.\n\n` +
      `For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}.\n\n` +
      `Thanks`
    );
    const teamsCalendarUrl = `https://outlook.office.com/calendar/0/deeplink/compose?subject=${title}&body=${body}&startdt=${start_date}T09:00:00&enddt=${end_date}T18:00:00&allday=true`;
    window.open(teamsCalendarUrl, "_blank", "noopener,noreferrer");
  };

  // 2. Download .ics iCalendar event (with Microsoft Teams Out-of-Office metadata)
  const downloadIcs = () => {
    const startFormatted = start_date.replace(/-/g, "");
    const endFormatted = end_date.replace(/-/g, "");
    const timeText = start_date === end_date ? `on ${start_date}` : `from ${start_date} to ${end_date}`;
    const managerContact = manager_email ? `${approver_name} (${manager_email})` : approver_name;
    const desc = `I will be on leave ${timeText}. For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}. Thanks`;

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
      `SUMMARY:${leave_type} (Out of Office)`,
      `DESCRIPTION:${desc}`,
      "STATUS:CONFIRMED",
      "TRANSP:OPAQUE",
      "X-MICROSOFT-CDO-BUSYSTATUS:OOF",
      "X-MICROSOFT-CDO-INTENDEDSTATUS:OOF",
      "X-MICROSOFT-CDO-ALLDAYEVENT:TRUE",
      "END:VEVENT",
      "END:VCALENDAR",
    ].join("\r\n");

    const blob = new Blob([icsData], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `leave-${start_date}-to-${end_date}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 3. Open pre-composed mailto
  const getMailtoUrl = () => {
    const timeText = start_date === end_date ? `on ${start_date}` : `from ${start_date} to ${end_date}`;
    const timeframe = start_date === end_date ? start_date : `${start_date} to ${end_date}`;
    const subject = encodeURIComponent(`Out of Office: ${timeframe}`);
    const managerContact = manager_email ? `${approver_name} (${manager_email})` : approver_name;
    const body = encodeURIComponent(
      `Hi Team,\n\n` +
      `I will be on leave ${timeText}\n\n` +
      `For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}.\n\n` +
      `Thanks`
    );
    return `mailto:team@hcservices.ae?subject=${subject}&body=${body}`;
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-emerald-500/30 bg-emerald-50/60 dark:bg-emerald-950/20 shadow-sm">
      <div className="flex items-center gap-2 border-b border-emerald-500/20 bg-emerald-100/50 dark:bg-emerald-900/30 px-3.5 py-2">
        <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
        <span className="font-display text-xs font-semibold text-emerald-900 dark:text-emerald-200">
          Leave Request Approved
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
          Would you like to mark this Out-of-Office on your Teams / Outlook calendar or notify your team?
        </p>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button
            size="sm"
            onClick={openTeamsCalendar}
            className="h-8 gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs cursor-pointer"
          >
            <Calendar className="size-3.5" />
            Calendar
            <ExternalLink className="size-3 opacity-70" />
          </Button>

          <a href={getMailtoUrl()} target="_blank" rel="noopener noreferrer">
            <Button
              size="sm"
              variant="outline"
              className="h-8 gap-1.5 text-xs border-border hover:bg-muted cursor-pointer"
            >
              <Mail className="size-3.5" />
              Email
            </Button>
          </a>
        </div>
      </div>
    </div>
  );
}
