export type NotificationModule =
  | "leave" | "attendance" | "regularization" | "permission" | "holiday" | "announcement" | "promotion"
  | "confirmation" | "payroll" | "system" | "timesheet" | "expense" | "separation" | "documents" | "birthday" | "security" | "facial_recognition";

export interface Notification {
  id:                 string;
  title:              string;
  message:            string;
  notification_type:  string;
  module:             NotificationModule;
  reference_id:       string;
  is_read:            boolean;
  /** The notice asks the person to act as an approver (a request is waiting for them), not about their own request. */
  is_for_approver?:   boolean;
  created_at:         string;
}

export interface NotificationListResponse {
  count:         number;
  page:          number;
  page_size:     number;
  total_pages:   number;
  unread_count:  number;
  results:       Notification[];
}

export interface UnreadCountResponse {
  unread_count: number;
}
