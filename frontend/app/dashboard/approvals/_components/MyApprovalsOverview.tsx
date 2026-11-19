"use client";

// The front door of /dashboard/approvals: what is waiting on this person, per workflow, with a way into each tab.
// It only counts what each workflow's own API returns for the signed-in user; it does not approve anything itself, and
// every action stays in its own tab under that workflow's own authorization. Workflows keep different assignment
// rules (see KIND_SCOPE_NOTES), which is why each line says how it is scoped.
import { useEffect, useState, type CSSProperties } from "react";
import { useApprovalOverview } from "@/hooks/useApprovalOverview";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import HrRequestsTab from "./HrRequestsTab";
import ApprovalWorkflowCard from "./ApprovalWorkflowCard";
import ApprovalWorkflowRow from "./ApprovalWorkflowRow";
import { ApprovalOverviewStyles } from "./approvalOverviewStyles";
import { PROFILE_CORRECTION_TOPIC } from "@/app/dashboard/ess/_components/ProfileCorrectionModal";
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

type LayoutKey = "cards" | "list";
const LAYOUT_STORAGE_KEY = "approvals-overview-layout";

/** The chosen layout is a per-person convenience kept in the browser; the page works without it. */
function readLayout(): LayoutKey {
  try { return window.localStorage.getItem(LAYOUT_STORAGE_KEY) === "list" ? "list" : "cards"; } catch { return "cards"; }
}

export default function MyApprovalsOverview({
  canApprove, canApproveAttendance, canApproveTimesheets, canSeePersonnel, canApproveFace, canRespondHrHelp = false, openHrRequestsInitially = false, onOpen,
}: MyApprovalsOverviewProps) {
  const [isMineOnly, setIsMineOnly] = useState(false);
  const [layout, setLayout] = useState<LayoutKey>("cards");
  useEffect(() => { setLayout(readLayout()); }, []);
  function chooseLayout(next: LayoutKey) {
    setLayout(next);
    try { window.localStorage.setItem(LAYOUT_STORAGE_KEY, next); } catch { /* a blocked store only means the choice is not remembered */ }
  }
  const [isCorrectionsOpen, setIsCorrectionsOpen] = useState(openHrRequestsInitially);
  // Anyone who answers HR Help tickets sees every ticket, so what is waiting is also theirs to act on.
  const openCorrections = useFetch<{ count: number }>(
    canRespondHrHelp ? `${API.hrHelp.list}?status=open&page_size=1&topic=${PROFILE_CORRECTION_TOPIC}` : null,
  );
  const correctionCount = openCorrections.data?.count ?? 0;
  useEffect(() => { if (openHrRequestsInitially) setIsCorrectionsOpen(true); }, [openHrRequestsInitially]);
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
      key: "profile_corrections", label: "Profile corrections",
      scope: "Changes employees ask HR to make to their profile. Everyone who answers HR Help tickets, and any full-access user, sees all of them.",
      pending: correctionCount, mine: correctionCount, section: "overview" as const,
      open: () => setIsCorrectionsOpen(open => !open),
    }] : []),
  ];

  const shown = isMineOnly ? rows.filter(row => row.mine === null || row.mine > 0) : rows;
  const actionLabelOf = (row: Row) => (row.key === "profile_corrections" && isCorrectionsOpen ? "Hide" : "Open");
  const runAction = (row: Row) => (row.open ? row.open() : onOpen(row.section));
  const totalWaiting = rows.reduce((sum, row) => sum + (row.pending ?? 0), 0);
  const totalMine = rows.reduce((sum, row) => sum + (row.mine ?? 0), 0);
  const workflowsWithWork = rows.filter(row => (row.mine ?? 0) > 0).length;
  const summary = [
    { label: "Waiting in total",     value: totalWaiting,      icon: "ti-hourglass",      accent: "#d97706" },
    { label: "Needs your action",    value: totalMine,         icon: "ti-bolt",           accent: "var(--brand)" },
    { label: "Workflows with work",  value: workflowsWithWork, icon: "ti-layout-list",    accent: "#0ea5e9" },
  ];

  return (
    <div>
      <ApprovalOverviewStyles />

      {!overview.isLoading && (
        <div className="ap-summary">
          {summary.map(item => (
            <div key={item.label} className="ap-tile" style={{ "--ap-accent": item.accent } as CSSProperties}>
              <span className="ap-icon"><i className={`ti ${item.icon}`} /></span>
              <div><b>{item.value}</b><span className="ap-tile-label">{item.label}</span></div>
            </div>
          ))}
        </div>
      )}

      <div className="ap-bar">
        <h2><i className="ti ti-inbox" /> My Approvals</h2>
        <div className="ap-tools">
          <div className="ap-views" role="group" aria-label="Layout">
            <button type="button" className={layout === "cards" ? "is-on" : ""} aria-pressed={layout === "cards"} onClick={() => chooseLayout("cards")}><i className="ti ti-layout-grid" /> Cards</button>
            <button type="button" className={layout === "list" ? "is-on" : ""} aria-pressed={layout === "list"} onClick={() => chooseLayout("list")}><i className="ti ti-list" /> List</button>
          </div>
          <label className={`ap-switch${isMineOnly ? " is-on" : ""}`}>
            <input type="checkbox" checked={isMineOnly} onChange={event => setIsMineOnly(event.target.checked)} />
            Only what I can act on
          </label>
        </div>
      </div>

      {overview.isLoading && <div className="ap-empty">Loading…</div>}
      {!overview.isLoading && shown.length === 0 && (
        <div className="ap-empty"><i className="ti ti-circle-check" />Nothing is waiting for you.</div>
      )}
      {!overview.isLoading && shown.length > 0 && layout === "cards" && (
        <div className="ap-grid">
          {shown.map(row => (
            <ApprovalWorkflowCard key={row.key} row={row} actionLabel={actionLabelOf(row)} onAction={() => runAction(row)} />
          ))}
        </div>
      )}
      {!overview.isLoading && shown.length > 0 && layout === "list" && (
        <>
          {[
            { title: "Needs your action", items: shown.filter(row => (row.mine ?? 0) > 0) },
            { title: "Everything else", items: shown.filter(row => (row.mine ?? 0) === 0) },
          ].filter(group => group.items.length > 0).map(group => (
            <section key={group.title} className="ap-group" aria-label={group.title}>
              <h3 className="ap-group-head">{group.title} <span>{group.items.length}</span></h3>
              <div className="ap-lines">
                {group.items.map(row => (
                  <ApprovalWorkflowRow key={row.key} row={row} actionLabel={actionLabelOf(row)} onAction={() => runAction(row)} />
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {canRespondHrHelp && isCorrectionsOpen && (
        <div className="card" style={{ marginTop: 16, padding: 16 }}>
          <HrRequestsTab title="Profile corrections" topic={PROFILE_CORRECTION_TOPIC} onChanged={openCorrections.refetch} />
        </div>
      )}
      <p className="ap-note">
        Counts show only what the server lets you see. Onboarding approvals are in Review &amp; Onboarding, and bank-change
        requests are in the employee record; they are not part of this list.
      </p>
    </div>
  );
}
