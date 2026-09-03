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

interface NotificationCenterProps {
  employeeId: string;
  onActionClick?: (prompt: string) => void;
}

export function NotificationCenter({ employeeId, onActionClick }: NotificationCenterProps) {
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

  const downloadCalendarInvite = (notif: AppNotification) => {
    const payload = notif.action_payload || {};
    const start = (payload.start_date || "2026-06-01").replace(/-/g, "");
    const end = (payload.end_date || "2026-06-05").replace(/-/g, "");
    const leaveType = payload.leave_type || "Annual Leave";
    const icsContent = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Bayan HR//Leave Calendar//EN",
      "BEGIN:VEVENT",
      `SUMMARY:${leaveType} (Approved)`,
      `DESCRIPTION:${notif.message}`,
      `DTSTART;VALUE=DATE:${start}`,
      `DTEND;VALUE=DATE:${end}`,
      "STATUS:CONFIRMED",
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
                        {isLeaveReq && <Clock className="size-4 text-amber-500" />}
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
                          <span className="text-[10px] text-muted-foreground whitespace-nowrap">
                            {n.created_at ? n.created_at.split(" ")[1]?.slice(0, 5) : ""}
                          </span>
                        </div>

                        <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
                          {n.message}
                        </p>

                        {/* Quick action triggers */}
                        <div className="mt-2.5 flex items-center gap-2">
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
                                variant="outline"
                                size="sm"
                                className="h-6 px-2 text-[11px] gap-1 cursor-pointer"
                                onClick={() => downloadCalendarInvite(n)}
                              >
                                <Calendar className="size-3" />
                                Add to Calendar
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-6 px-2 text-[11px] gap-1 cursor-pointer text-muted-foreground"
                                onClick={() => {
                                  const subject = encodeURIComponent("Approved Leave Notification");
                                  const body = encodeURIComponent(
                                    `Hi HR Team,\n\nPlease note my approved leave:\n${n.message}\n\nThank you.`
                                  );
                                  window.open(`mailto:hr@hcservices.ae?subject=${subject}&body=${body}`);
                                }}
                              >
                                <Mail className="size-3" />
                                Email HR
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
