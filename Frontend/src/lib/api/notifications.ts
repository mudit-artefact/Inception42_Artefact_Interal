import { apiRequest } from "./client";
import { isApiConfigured } from "./config";

export interface AppNotification {
  id: number;
  recipient_id: string;
  sender_id?: string | null;
  event_type: string;
  title: string;
  message: string;
  action_url?: string;
  action_payload?: Record<string, any>;
  is_read: boolean;
  created_at: string;
}

export interface NotificationListResponse {
  employee_id: string;
  unread_count: number;
  notifications: AppNotification[];
}

export async function fetchNotifications(employeeId: string): Promise<NotificationListResponse> {
  if (!isApiConfigured()) {
    return { employee_id: employeeId, unread_count: 0, notifications: [] };
  }

  try {
    return await apiRequest<NotificationListResponse>(`/api/notifications/${encodeURIComponent(employeeId)}`);
  } catch (err) {
    console.warn(`Failed to fetch notifications for ${employeeId}:`, err);
    return { employee_id: employeeId, unread_count: 0, notifications: [] };
  }
}

export async function markNotificationAsRead(notificationId: number): Promise<void> {
  if (!isApiConfigured()) return;
  try {
    await apiRequest(`/api/notifications/${notificationId}/read`, { method: "POST" });
  } catch (err) {
    console.warn(`Failed to mark notification ${notificationId} as read:`, err);
  }
}

export async function markAllNotificationsAsRead(employeeId: string): Promise<void> {
  if (!isApiConfigured()) return;
  try {
    await apiRequest(`/api/notifications/${encodeURIComponent(employeeId)}/read-all`, { method: "POST" });
  } catch (err) {
    console.warn(`Failed to mark all notifications for ${employeeId} as read:`, err);
  }
}
