import { Bell, Calendar, CheckCircle2, Clock, Mail, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  AppNotification,
  fetchNotifications,
  markAllNotificationsAsRead,
  markNotificationAsRead,
} from "@/lib/api/notifications";
import type { EmployeeProfile } from "@/lib/api/types";

interface NotificationCenterProps {
  employeeId: string;
  employee?: EmployeeProfile | undefined;
  onActionClick?: (prompt: string) => void;
}

function getLeaveNotificationDetails(notif: AppNotification, fallbackEmployee?: EmployeeProfile) {
  const payload = notif.action_payload || {};
  let startDate: string | undefined = payload.start_date;
  let endDate: string | undefined = payload.end_date;
  let leaveType: string | undefined = payload.leave_type;
  let days: string | number | undefined = payload.days_requested;
  let managerName: string | undefined = payload.manager_name || payload.approver_name;
  let managerEmail: string | undefined = payload.manager_email;
  let employeeName: string | undefined = payload.employee_name || fallbackEmployee?.name;

  if (!startDate || !endDate || !leaveType || !managerName) {
    const msg = notif.message || "";
    const dateMatch = msg.match(/\((\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})\)/i);
    if (dateMatch) {
      startDate = startDate || dateMatch[1];
      endDate = endDate || dateMatch[2];
    }
    const daysMatch = msg.match(/(\d+(?:\.\d+)?)\s*working days?/i);
    if (daysMatch) {
      days = days || daysMatch[1];
    }
    const typeMatch = msg.match(/working days? of ([^()]+?)\s*\(/i);
    if (typeMatch) {
      leaveType = leaveType || typeMatch[1].trim();
    }
    const approverMatch = msg.match(/approved by\s+([^.]+)/i);
    if (approverMatch) {
      managerName = managerName || approverMatch[1].trim();
    }
  }

  if (!managerName && fallbackEmployee?.manager) {
    managerName = fallbackEmployee.manager;
  }

  const cleanDays = days ? `${days} working day${Number(days) === 1 ? "" : "s"}` : "";
  const timeframe = startDate && endDate
    ? startDate === endDate
      ? startDate
      : `${startDate} to ${endDate}`
    : startDate || "this upcoming period";

  const timeText = startDate && endDate && startDate !== endDate
    ? `from ${startDate} to ${endDate}`
    : (startDate ? `on ${startDate}` : "during this period");

  return {
    startDate: startDate || "2026-06-01",
    endDate: endDate || startDate || "2026-06-05",
    timeframe,
    timeText,
    leaveType: leaveType || "Annual Leave",
    days: cleanDays,
    managerName: managerName || "my manager",
    managerEmail: managerEmail || "",
    employeeName: employeeName || "Employee",
  };
}

function normalizeDate(dateStr?: string | null): Date | null {
  if (!dateStr) return null;
  let normalized = dateStr.trim();
  // If stored as naive UTC "YYYY-MM-DD HH:MM:SS", convert to ISO "YYYY-MM-DDTHH:MM:SSZ"
  if (/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$/.test(normalized)) {
    normalized = normalized.replace(/\s+/, "T") + "Z";
  } else if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(normalized)) {
    normalized = normalized + "Z";
  }
  const d = new Date(normalized);
  return isNaN(d.getTime()) ? null : d;
}

function formatNotificationTime(dateStr?: string | null): string {
  const d = normalizeDate(dateStr);
  if (!d) return "";

  const today = new Date();
  const isSameDay = d.toDateString() === today.toDateString();

  return isSameDay
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function getFullNotificationTime(dateStr?: string | null): string {
  const d = normalizeDate(dateStr);
  return d ? d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" }) : "";
}

export function NotificationCenter({ employeeId, employee, onActionClick }: NotificationCenterProps) {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const loadNotifications = async () => {
    if (!employeeId) return;
    setIsLoading(true);
    try {
      const res = await fetchNotifications(employeeId);
      setNotifications(res.notifications || []);
      setUnreadCount(res.unread_count || 0);
    } catch (err) {
      console.error("Error loading notifications:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadNotifications();
    const interval = setInterval(loadNotifications, 8000);
    return () => clearInterval(interval);
  }, [employeeId]);

  const handleMarkAsRead = async (id: number) => {
    await markNotificationAsRead(id);
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));
  };

  const handleMarkAllRead = async () => {
    await markAllNotificationsAsRead(employeeId);
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);
  };

  const openTeamsCalendar = (notif: AppNotification) => {
    const details = getLeaveNotificationDetails(notif, employee);
    const title = encodeURIComponent(`${details.leaveType} (Out of Office)`);
    const managerContact = details.managerEmail
      ? `${details.managerName} (${details.managerEmail})`
      : details.managerName;
    const body = encodeURIComponent(
      `I will be on leave ${details.timeText}.\n\n` +
      `For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}.\n\n` +
      `Thanks`
    );
    const url = `https://outlook.office.com/calendar/0/deeplink/compose?subject=${title}&body=${body}&startdt=${details.startDate}T09:00:00&enddt=${details.endDate}T18:00:00&allday=true`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const downloadCalendarInvite = (notif: AppNotification) => {
    const details = getLeaveNotificationDetails(notif, employee);
    const start = details.startDate.replace(/-/g, "");
    const end = details.endDate.replace(/-/g, "");
    const managerContact = details.managerEmail
      ? `${details.managerName} (${details.managerEmail})`
      : details.managerName;
    const desc = `I will be on leave ${details.timeText}. For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}. Thanks`;
    const icsContent = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Dalīl//Leave Calendar//EN",
      "BEGIN:VEVENT",
      `SUMMARY:${details.leaveType} (Out of Office)`,
      `DESCRIPTION:${desc}`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${end}`,
      "STATUS:CONFIRMED",
      "TRANSP:OPAQUE",
      "X-MICROSOFT-CDO-BUSYSTATUS:OOF",
      "X-MICROSOFT-CDO-INTENDEDSTATUS:OOF",
      "X-MICROSOFT-CDO-ALLDAYEVENT:TRUE",
      "END:VEVENT",
      "END:VCALENDAR",
    ].join("\r\n");

    const blob = new Blob([icsContent], { type: "text/calendar;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", `leave-${start}-${end}.ics`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="icon-sm"
          className="relative cursor-pointer hover:bg-muted"
          aria-label="Open notifications"
        >
          <Bell className="size-4 text-muted-foreground" />
          {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold text-destructive-foreground animate-in zoom-in-50">
              {unreadCount > 9 ? "9+" : unreadCount}
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[360px] p-0 shadow-lg sm:w-[400px]">
        <div className="flex items-center justify-between border-b px-4 py-2.5 bg-muted/40">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm">Notifications</span>
            {unreadCount > 0 && (
              <Badge variant="secondary" className="px-1.5 py-0 text-[11px] font-medium">
                {unreadCount} new
              </Badge>
            )}
          </div>
          {unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleMarkAllRead}
              className="h-7 text-xs text-muted-foreground hover:text-foreground cursor-pointer"
            >
              Mark all read
            </Button>
          )}
        </div>

        <ScrollArea className="max-h-[380px] divide-y">
          {notifications.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
              <Bell className="size-8 stroke-[1.25] text-muted-foreground/40 mb-2" />
              <p className="text-sm font-medium">No notifications yet</p>
              <p className="text-xs text-muted-foreground/70 mt-0.5">
                Leave applications and manager decisions will appear here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {notifications.map((n) => {
                const isLeaveReq = n.event_type === "LEAVE_REQUESTED";
                const isApproved = n.event_type === "LEAVE_APPROVED";
                const isRejected = n.event_type === "LEAVE_REJECTED";

                return (
                  <div
                    key={n.id}
                    className={`p-3.5 transition-colors hover:bg-muted/40 ${
                      !n.is_read ? "bg-primary/5" : ""
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <div className="mt-0.5 shrink-0">
                        {isLeaveReq && <Clock className="size-4 text-primary" />}
                        {isApproved && <CheckCircle2 className="size-4 text-emerald-500" />}
                        {isRejected && <XCircle className="size-4 text-rose-500" />}
                        {!isLeaveReq && !isApproved && !isRejected && (
                          <Bell className="size-4 text-primary" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <p className="text-xs font-semibold leading-none truncate text-foreground">
                            {n.title}
                          </p>
                          <span
                            className="text-[10px] text-muted-foreground whitespace-nowrap"
                            title={getFullNotificationTime(n.created_at)}
                          >
                            {formatNotificationTime(n.created_at)}
                          </span>
                        </div>

                        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                          {n.message}
                        </p>

                        {/* Quick action triggers */}
                        <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                          {isLeaveReq && onActionClick && (
                            <Button
                              variant="secondary"
                              size="sm"
                              className="h-6 px-2 text-[11px] font-medium cursor-pointer"
                              onClick={() => {
                                setIsOpen(false);
                                onActionClick("What leave requests do I need to approve?");
                                handleMarkAsRead(n.id);
                              }}
                            >
                              Review & Decide
                            </Button>
                          )}

                          {isApproved && (
                            <>
                              <Button
                                size="sm"
                                className="h-6 px-2 text-[11px] gap-1 cursor-pointer bg-emerald-600 hover:bg-emerald-700 text-white"
                                onClick={() => openTeamsCalendar(n)}
                              >
                                <Calendar className="size-3" />
                                Calendar
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-[11px] gap-1 cursor-pointer text-muted-foreground hover:text-foreground"
                                onClick={() => {
                                  const details = getLeaveNotificationDetails(n, employee);
                                  const subject = encodeURIComponent(`Out of Office: ${details.timeframe}`);
                                  const managerContact = details.managerEmail
                                    ? `${details.managerName} (${details.managerEmail})`
                                    : details.managerName;
                                  const body = encodeURIComponent(
                                    `Hi Team,\n\n` +
                                    `I will be on leave ${details.timeText}\n\n` +
                                    `For any queries or urgent matters during my absence, please reach out to my manager, ${managerContact}.\n\n` +
                                    `Thanks`
                                  );
                                  window.open(`mailto:team@hcservices.ae?subject=${subject}&body=${body}`);
                                }}
                              >
                                <Mail className="size-3" />
                                Email
                              </Button>
                            </>
                          )}

                          {!n.is_read && (
                            <button
                              type="button"
                              onClick={() => handleMarkAsRead(n.id)}
                              className="ml-auto text-[11px] text-muted-foreground hover:text-foreground cursor-pointer underline-offset-2 hover:underline"
                            >
                              Mark read
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
