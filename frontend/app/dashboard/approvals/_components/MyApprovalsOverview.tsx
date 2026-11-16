"use client";

// The front door of /dashboard/approvals: what is waiting on this person, per workflow, with a way into each tab.
// It only counts what each workflow's own API returns for the signed-in user; it does not approve anything itself, and
// every action stays in its own tab under that workflow's own authorization. Workflows keep different assignment
// rules (see KIND_SCOPE_NOTES), which is why each line says how it is scoped.
import { useEffect, useState } from "react";
import { useApprovalOverview } from "@/hooks/useApprovalOverview";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import HrRequestsTab from "./HrRequestsTab";
import { useTimesheetPending } from "@/hooks/useTimesheetQueue";
import { KIND_LABELS, KIND_SCOPE_NOTES } from "@/lib/approvalOverview";
import type { ApprovalSectionKey } from "@/lib/approvalSections";

interface MyApprovalsOverviewProps {
  canApprove: boolean;
  canApproveAttendance: boolean;
  canApproveTimesheets: boolean;
  canSeePersonnel: boolean;
  canApproveFace: boolean;
  /** Staff who answer HR Help tickets (profile corrections etc.): adds an "HR requests" row that opens the queue below the table. */
  canRespondHrHelp?: boolean;
  /** Show the HR requests queue straight away (a link such as the new-ticket bell notice asked for it). */
  openHrRequestsInitially?: boolean;
  onOpen: (section: ApprovalSectionKey) => void;
}

interface Row {
  key: string;
  label: string;
  scope: string;
  pending: number | null;
  mine: number | null;
  section: ApprovalSectionKey;
  /** Overrides going to a tab: the row opens something in place instead. */
  open?: () => void;
}

export default function MyApprovalsOverview({
  canApprove, canApproveAttendance, canApproveTimesheets, canSeePersonnel, canApproveFace, canRespondHrHelp = false, openHrRequestsInitially = false, onOpen,
}: MyApprovalsOverviewProps) {
  const [isMineOnly, setIsMineOnly] = useState(false);
  const [isHrRequestsOpen, setIsHrRequestsOpen] = useState(openHrRequestsInitially);
  // Anyone who answers HR Help tickets sees every ticket, so what is waiting is also theirs to act on.
  const openTickets = useFetch<{ count: number }>(canRespondHrHelp ? `${API.hrHelp.list}?status=open&page_size=1` : null);
  const openTicketCount = openTickets.data?.count ?? 0;
  useEffect(() => { if (openHrRequestsInitially) setIsHrRequestsOpen(true); }, [openHrRequestsInitially]);
  const overview = useApprovalOverview({ includeTeam: canApprove, includeFace: canApproveFace });
  const timesheetsWaiting = useTimesheetPending(canApproveTimesheets);

  const rows: Row[] = [
    ...(canApprove ? overview.team.map(count => ({
      key: count.kind, label: KIND_LABELS[count.kind], scope: KIND_SCOPE_NOTES[count.kind],
      pending: count.pending, mine: count.needsMyAction, section: "approvals" as const,
    })) : []),
    ...(canApproveFace ? [{
      key: "face", label: "Face ID registration",
      scope: "Employees assigned to you; with no assigned HR, employees on your branch. A full-access user sees all.",
      pending: overview.faceVisible, mine: overview.faceAssignedToMe, section: "face_registration" as const,
    }] : []),
    ...(canApproveAttendance ? [{
      key: "attendance", label: "Attendance approval", scope: "Cycle sign-off for your team or payroll scope. Open the tab to see what is due.",
      pending: null, mine: null, section: "attendance" as const,
    }] : []),
    // The timesheet queue is exactly the sheets this person may decide, so what is waiting is also what is theirs to act on.
    ...(canApproveTimesheets ? [{
      key: "timesheets", label: "Timesheets", scope: "Weekly timesheets from your direct reports, or assigned to you as approver; HR within their scope.",
      pending: timesheetsWaiting, mine: timesheetsWaiting, section: "timesheets" as const,
    }] : []),
    ...(canSeePersonnel ? [{
      key: "personnel", label: "Personnel actions", scope: "Promotions, transfers and similar actions at your stage of the chain. Open the tab to see what is due.",
      pending: null, mine: null, section: "personnel" as const,
    }] : []),
    ...(canRespondHrHelp ? [{
      key: "hr_requests", label: "HR requests",
      scope: "Profile corrections and other questions employees send to HR. Everyone who answers them, and any full-access user, sees all of them.",
      pending: openTicketCount, mine: openTicketCount, section: "overview" as const,
      open: () => setIsHrRequestsOpen(open => !open),
    }] : []),
  ];

  const shown = isMineOnly ? rows.filter(row => row.mine === null || row.mine > 0) : rows;

  return (
    <div className="card">
      <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="card-title"><i className="ti ti-inbox" /> My Approvals</div>
        <label style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <input type="checkbox" checked={isMineOnly} onChange={event => setIsMineOnly(event.target.checked)} />
          Only what I can act on
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>Workflow</th><th>Waiting</th><th>For me to act on</th><th>Who sees it</th><th /></tr>
          </thead>
          <tbody>
            {overview.isLoading && <tr><td colSpan={5} style={{ textAlign: "center", padding: 24 }}>Loading…</td></tr>}
            {!overview.isLoading && shown.length === 0 && (
              <tr><td colSpan={5} style={{ textAlign: "center", padding: 24 }}>Nothing is waiting for you.</td></tr>
            )}
            {!overview.isLoading && shown.map(row => (
              <tr key={row.key}>
                <td style={{ fontWeight: 500 }}>{row.label}</td>
                <td>{row.pending ?? "—"}</td>
                <td>{row.mine ?? "—"}</td>
                <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{row.scope}</td>
                <td><button className="btn btn-outline btn-sm" onClick={() => (row.open ? row.open() : onOpen(row.section))}>{row.key === "hr_requests" && isHrRequestsOpen ? "Hide" : "Open"}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canRespondHrHelp && isHrRequestsOpen && <div style={{ padding: "0 16px 16px" }}><HrRequestsTab onChanged={openTickets.refetch} /></div>}
      <p style={{ fontSize: 11, color: "var(--on-variant)", padding: "8px 16px 14px", margin: 0 }}>
        Counts show only what the server lets you see. Onboarding approvals are in Review &amp; Onboarding, and bank-change
        requests are in the employee record; they are not part of this list.
      </p>
    </div>
  );
}
