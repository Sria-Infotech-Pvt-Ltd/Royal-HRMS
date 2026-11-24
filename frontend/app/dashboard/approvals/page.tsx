"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TeamApprovalsSection from "./_components/TeamApprovalsSection";
import AttendanceApprovalTab from "./_components/AttendanceApprovalTab";
import FaceRegistrationApprovalsTab from "./_components/FaceRegistrationApprovalsTab";
import PersonnelActionsTab from "./_components/PersonnelActionsTab";
import TimesheetApprovalsTab from "./_components/TimesheetApprovalsTab";
import MyApprovalsOverview from "./_components/MyApprovalsOverview";
import { isUnrestrictedUser } from "@/lib/auth";
import { approvalSectionsFor, sectionFromLink, type ApprovalSectionKey } from "@/lib/approvalSections";
import { parseApprovalsLink } from "@/lib/approvalLink";
import { useT } from "@/hooks/useI18n";

type Section = ApprovalSectionKey;

export default function ApprovalsPage() {
  const t = useT();
  const user = useCurrentUser();
  const [section, setSection] = useState<Section>("overview");
  const canApprove      = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "separation.approve");
  const canApproveFace  = usePermission("facial_recognition.approve");
  // employees.approve = HR step, payroll.edit = Payroll Admin step, employees.raise_action =
  // a manager following the requests they raised. The server decides who may act on what.
  const canSeePersonnel = useAnyPermission("employees.approve", "payroll.edit", "employees.raise_action");
  const hasPayrollEdit  = usePermission("payroll.edit");
  // The HR Help queue: people who answer tickets, and full-access users (superuser / settings.edit) who see everything.
  const holdsHrHelpRespond = usePermission("hr_help.respond");
  const canRespondHrHelp = holdsHrHelpRespond || isUnrestrictedUser(user);
  // Managers, superusers, and anyone with payroll.edit (payroll admins) get this tab — it's the only place attendance-cycle
  // sign-off lives now that Leave Management no longer has its own "Attendance Approvals" tab. It is payroll.edit, not
  // payroll.view, because that is what the server requires (payroll/views/attendance_approval.py HR_PERMISSION): someone
  // with payroll.view only used to see the tab and then be told "Access denied".
  const canApproveAttendance =
    user?.can_manage_team === true ||
    user?.is_superuser === true ||
    hasPayrollEdit;

  // Timesheets: the assigned approver is usually the reporting manager (a team seat), or HR (leave.approve is what the HR
  // fallback is found by; timesheet.approve is the explicit grant). The server lists only the sheets this person may decide.
  const holdsTimesheetApprove = useAnyPermission("timesheet.approve", "leave.approve");
  const canApproveTimesheets = user?.can_manage_team === true || user?.is_superuser === true || holdsTimesheetApprove;

  const sections = useMemo(
    () => approvalSectionsFor({ canApprove, canApproveAttendance, canApproveTimesheets, canSeePersonnel, canApproveFace, canRespondHrHelp }),
    [canApprove, canApproveAttendance, canApproveTimesheets, canApproveFace, canSeePersonnel, canRespondHrHelp],
  );

  useEffect(() => {
    if (sections.length > 0 && !sections.some(s => s.key === section)) {
      setSection(sections[0].key);
    }
  }, [section, sections]);

  // A link such as a timesheet bell notice opens a named tab (?section=timesheets), once this person's tabs are known.
  const linkParams = useSearchParams();
  const linkedSection = linkParams.get("section");
  const linkedFilters = useMemo(() => parseApprovalsLink(linkParams), [linkParams]);
  useEffect(() => {
    const wanted = sectionFromLink(linkedSection, sections);
    if (wanted) setSection(wanted);
  }, [linkedSection, sections]);
  // ?section=hr_requests (the bell notice, the dashboard row) opens the overview with the HR requests queue already showing.
  const opensHrRequests = linkedSection === "hr_requests" && canRespondHrHelp;
  useEffect(() => {
    if (opensHrRequests) setSection("overview");
  }, [opensHrRequests]);

  return (
    <div>
      <div className="tabs">
        {sections.map(s => (
          <button
            key={s.key}
            suppressHydrationWarning
            onClick={() => setSection(s.key)}
            className={`tab${section === s.key ? " active" : ""}`}
          >
            <i className={`ti ${s.icon}`} style={{ marginRight: 5 }} />
            {t(s.label)}
          </button>
        ))}
      </div>

      {section === "overview" && (
        <MyApprovalsOverview
          canApprove={canApprove} canApproveAttendance={canApproveAttendance} canApproveTimesheets={canApproveTimesheets}
          canSeePersonnel={canSeePersonnel} canApproveFace={canApproveFace} canRespondHrHelp={canRespondHrHelp}
          openHrRequestsInitially={opensHrRequests} onOpen={setSection}
        />
      )}
      {section === "timesheets"        && canApproveTimesheets && <TimesheetApprovalsTab />}
      {section === "approvals"         && canApprove           && <TeamApprovalsSection initialFilters={linkedFilters} />}
      {section === "attendance"        && canApproveAttendance && <div className="settings-card"><AttendanceApprovalTab /></div>}
      {section === "personnel"         && canSeePersonnel      && <PersonnelActionsTab />}
      {section === "face_registration" && canApproveFace        && <div className="settings-card"><FaceRegistrationApprovalsTab /></div>}
    </div>
  );
}
