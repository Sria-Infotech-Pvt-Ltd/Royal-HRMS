export type FeedbackStatus = "pending" | "provided" | "declined";

export interface FeedbackRequest {
  id: string;
  requester_name: string;
  recipient_name: string;
  cycle_label: string;
  topic: string;
  status: FeedbackStatus;
  status_display: string;
  response: string;
  created_at: string;
  responded_at: string | null;
  /** True only for the recipient while the request is still pending. */
  can_respond: boolean;
}

export interface FeedbackColleague {
  id: string;
  name: string;
  employee_id: string;
  relation: "Reporting manager" | "Peer" | "Direct report";
}
