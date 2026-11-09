// Which tabs the Approvals page shows. Pure, so every combination of permissions can be tested without a browser.
// Each tab is gated by what its own workflow's API requires; the server still enforces all of it.

export type ApprovalSectionKey = "overview" | "approvals" | "attendance" | "personnel" | "face_registration";

export interface ApprovalAccess {
  /** leave / expense / WFH / separation / regularization approvals (Team Approvals). */
  canApprove: boolean;
  canApproveAttendance: boolean;
  canSeePersonnel: boolean;
  /** facial_recognition.approve — Face ID registrations. */
  canApproveFace: boolean;
}

export interface ApprovalSection {
  key: ApprovalSectionKey;
  label: string;
  icon: string;
}

export function approvalSectionsFor(access: ApprovalAccess): ApprovalSection[] {
  const sections: ApprovalSection[] = [
    ...(access.canApprove ? [{ key: "approvals" as const, label: "Team Approvals", icon: "ti-checks" }] : []),
    ...(access.canApproveAttendance ? [{ key: "attendance" as const, label: "Attendance Approval", icon: "ti-calendar-check" }] : []),
    ...(access.canSeePersonnel ? [{ key: "personnel" as const, label: "Personnel Actions", icon: "ti-bolt" }] : []),
    ...(access.canApproveFace ? [{ key: "face_registration" as const, label: "Face Registration", icon: "ti-face-id" }] : []),
  ];
  // The overview is the front door to the others: only worth showing when there is something to open.
  return sections.length > 0 ? [{ key: "overview", label: "My Approvals", icon: "ti-inbox" }, ...sections] : sections;
}
