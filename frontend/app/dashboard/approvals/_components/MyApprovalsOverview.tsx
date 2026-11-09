"use client";

// The front door of /dashboard/approvals: what is waiting on this person, per workflow, with a way into each tab.
// It only counts what each workflow's own API returns for the signed-in user; it does not approve anything itself, and
// every action stays in its own tab under that workflow's own authorization. Workflows keep different assignment
// rules (see KIND_SCOPE_NOTES), which is why each line says how it is scoped.
import { useState } from "react";
import { useApprovalOverview } from "@/hooks/useApprovalOverview";
import { KIND_LABELS, KIND_SCOPE_NOTES } from "@/lib/approvalOverview";
import type { ApprovalSectionKey } from "@/lib/approvalSections";

interface MyApprovalsOverviewProps {
  canApprove: boolean;
  canApproveAttendance: boolean;
  canSeePersonnel: boolean;
  canApproveFace: boolean;
  onOpen: (section: ApprovalSectionKey) => void;
}

interface Row {
  key: string;
  label: string;
  scope: string;
  pending: number | null;
  mine: number | null;
  section: ApprovalSectionKey;
}

export default function MyApprovalsOverview({ canApprove, canApproveAttendance, canSeePersonnel, canApproveFace, onOpen }: MyApprovalsOverviewProps) {
  const [isMineOnly, setIsMineOnly] = useState(false);
  const overview = useApprovalOverview({ includeTeam: canApprove, includeFace: canApproveFace });

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
    ...(canSeePersonnel ? [{
      key: "personnel", label: "Personnel actions", scope: "Promotions, transfers and similar actions at your stage of the chain. Open the tab to see what is due.",
      pending: null, mine: null, section: "personnel" as const,
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
                <td><button className="btn btn-outline btn-sm" onClick={() => onOpen(row.section)}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 11, color: "var(--on-variant)", padding: "8px 16px 14px", margin: 0 }}>
        Counts show only what the server lets you see. Onboarding approvals are in Review &amp; Onboarding, and bank-change
        requests are in the employee record; they are not part of this list.
      </p>
    </div>
  );
}
