export type NotificationModule =
  | "leave" | "attendance" | "regularization" | "permission" | "holiday" | "announcement" | "promotion";

export interface Notification {
  id:                 string;
  title:              string;
  message:            string;
  notification_type:  string;
  module:             NotificationModule;
  reference_id:       string;
  is_read:            boolean;
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
