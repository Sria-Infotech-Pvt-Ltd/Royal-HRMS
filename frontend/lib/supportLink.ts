// Where the footer's Support link (and an info page's "Contact HR" button) should lead for a given person. Pure, so every role can be tested.
//
// The only help channel the app has is the HR help ticket form in a person's own workspace. That is right for employees and
// managers, who raise tickets. It makes no sense for the people who ANSWER tickets (hr_help.respond) or have full access: they are
// HR, so they are sent to the queue of requests on the Approvals page instead and are not offered a "contact HR" button.

import { isUnrestrictedUser, type UserInfo } from "@/lib/auth";

export const HR_HELP_PATH = "/dashboard/ess?tab=hrHelp";
export const HR_REQUESTS_QUEUE_PATH = "/dashboard/approvals";

export interface SupportTarget {
  path: string;
  /** The footer link's text. */
  footerLabel: string;
  /** Whether this person raises tickets to HR (and so is offered "Contact HR"). */
  canRaiseHrHelp: boolean;
}

export function supportTargetFor(user: UserInfo | null): SupportTarget {
  const answersTickets = isUnrestrictedUser(user) || (user?.permissions?.includes("hr_help.respond") ?? false);
  if (answersTickets) return { path: HR_REQUESTS_QUEUE_PATH, footerLabel: "HR requests", canRaiseHrHelp: false };
  return { path: HR_HELP_PATH, footerLabel: "Support", canRaiseHrHelp: true };
}
