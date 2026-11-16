// Which tabs the Approvals page shows. Pure, so every combination of permissions can be tested without a browser.
// Each tab is gated by what its own workflow's API requires; the server still enforces all of it.

export type ApprovalSectionKey = "overview" | "approvals" | "attendance" | "timesheets" | "personnel" | "face_registration";

export interface ApprovalAccess {
  /** leave / expense / WFH / separation / regularization approvals (Team Approvals). */
  canApprove: boolean;
  canApproveAttendance: boolean;
  /** Weekly timesheets: managers, people holding timesheet.approve (or leave.approve, the HR fallback) and superusers. The
   *  server limits the list to the sheets this person may actually decide, so a person with nothing waiting sees it empty. */
  canApproveTimesheets: boolean;
  canSeePersonnel: boolean;
  /** facial_recognition.approve — Face ID registrations. */
  canApproveFace: boolean;
  /** hr_help.respond, or full access (superuser / settings.edit): the queue of every employee's HR Help ticket, profile corrections
   *  included. It is a row of the My Approvals overview (opened in place), not a tab of its own. */
  canRespondHrHelp?: boolean;
}

export interface ApprovalSection {
  key: ApprovalSectionKey;
  label: string;
  icon: string;
}

/** The tab a link asks for (?section=timesheets), if this person has it; null otherwise, so a link never opens a tab they lack. */
export function sectionFromLink(requested: string | null, sections: ApprovalSection[]): ApprovalSectionKey | null {
  return sections.find(section => section.key === requested)?.key ?? null;
}

export function approvalSectionsFor(access: ApprovalAccess): ApprovalSection[] {
  const sections: ApprovalSection[] = [
    ...(access.canApprove ? [{ key: "approvals" as const, label: "Team Approvals", icon: "ti-checks" }] : []),
    ...(access.canApproveAttendance ? [{ key: "attendance" as const, label: "Attendance Approval", icon: "ti-calendar-check" }] : []),
    ...(access.canApproveTimesheets ? [{ key: "timesheets" as const, label: "Timesheets", icon: "ti-clock-check" }] : []),
    ...(access.canSeePersonnel ? [{ key: "personnel" as const, label: "Personnel Actions", icon: "ti-bolt" }] : []),
    ...(access.canApproveFace ? [{ key: "face_registration" as const, label: "Face Registration", icon: "ti-face-id" }] : []),
  ];
  // The overview is the front door to the others: only worth showing when there is something to open.
  return sections.length > 0 || access.canRespondHrHelp ? [{ key: "overview", label: "My Approvals", icon: "ti-inbox" }, ...sections] : sections;
}
