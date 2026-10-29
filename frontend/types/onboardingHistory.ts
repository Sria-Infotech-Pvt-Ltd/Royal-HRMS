export type OnboardingEventType =
  | "initiated" | "email_sent" | "email_failed" | "email_resent" | "email_corrected"
  | "link_opened" | "first_login" | "password_set" | "activated";

export type OnboardingStateCode =
  | "active" | "email_failed" | "link_expired" | "awaiting_login" | "link_opened" | "not_logged_in";

export interface OnboardingTimelineItem {
  id: string;
  event: OnboardingEventType;
  label: string;
  at: string;
  actor_name: string | null;
  detail: string;
}

export interface OnboardingHistory {
  employee_name: string;
  email: string;
  is_onboarding: boolean;
  state: { code: OnboardingStateCode; message: string; can_resend: boolean };
  timeline: OnboardingTimelineItem[];
  resend_limit_per_hour: number;
  invite_status: string | null;
  invite_sent_at: string | null;
  invite_expires_at: string | null;
}
