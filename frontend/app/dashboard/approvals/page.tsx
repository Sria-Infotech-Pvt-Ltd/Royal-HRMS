"use client";

import { useEffect, useMemo, useState } from "react";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import { useHasModule } from "@/lib/modulesContext";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TeamApprovalsSection from "./_components/TeamApprovalsSection";
import AttendanceApprovalTab from "./_components/AttendanceApprovalTab";
import FaceRegistrationApprovalsTab from "./_components/FaceRegistrationApprovalsTab";
import DelegationsSection from "./_components/DelegationsSection";
import LeaveCancellationsSection from "./_components/LeaveCancellationsSection";

type Section = "approvals" | "attendance" | "face_registration" | "cancellations" | "delegation";

export default function ApprovalsPage() {
  const user = useCurrentUser();
  const [section, setSection] = useState<Section>("approvals");
  const canApprove      = useAnyPermission("leave.approve", "expenses.approve", "attendance.create", "separation.approve");
  const faceOn          = useHasModule("face_attendance");
  const attendanceOn    = useHasModule("attendance");
  const canApproveFace  = usePermission("facial_recognition.approve") && faceOn;
  const hasPayrollView  = usePermission("payroll.view");
  const canApproveLeave = usePermission("leave.approve");
  const hasAttCreate    = usePermission("attendance.create");
  const hasAttEdit      = usePermission("attendance.edit");
  // Mirrors the backend: leave.approve, or attendance.create held by attendance staff.
  const canDelegate     = canApproveLeave || (hasAttCreate && (hasAttEdit || user?.can_manage_team === true || user?.can_manage_branch === true || user?.is_superuser === true));
  // Managers, superusers, and anyone with payroll.view (payroll admins and HR
  // alike) get this tab — it's the only place attendance-cycle sign-off lives
  // now that Leave Management no longer has its own "Attendance Approvals" tab.
  const canApproveAttendance = attendanceOn && (
    user?.can_manage_team === true ||
    user?.is_superuser === true ||
    hasPayrollView);

  const sections: { key: Section; label: string; icon: string }[] = useMemo(() => [
    ...(canApprove           ? [{ key: "approvals"         as Section, label: "Team Approvals",      icon: "ti-checks"         }] : []),
    ...(canApproveAttendance ? [{ key: "attendance"         as Section, label: "Attendance Approval", icon: "ti-calendar-check" }] : []),
    ...(canApproveFace       ? [{ key: "face_registration"  as Section, label: "Face Registration",   icon: "ti-face-id"        }] : []),
    ...(canApproveLeave      ? [{ key: "cancellations"      as Section, label: "Leave Cancellations", icon: "ti-calendar-x"     }] : []),
    ...(canDelegate          ? [{ key: "delegation"         as Section, label: "Delegation",          icon: "ti-user-share"     }] : []),
  ], [canApprove, canApproveAttendance, canApproveFace, canApproveLeave, canDelegate]);

  useEffect(() => {
    if (sections.length > 0 && !sections.some(s => s.key === section)) {
      setSection(sections[0].key);
    }
  }, [section, sections]);

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
            {s.label}
          </button>
        ))}
      </div>

      {section === "approvals"         && canApprove           && <TeamApprovalsSection />}
      {section === "attendance"        && canApproveAttendance && <div className="settings-card"><AttendanceApprovalTab /></div>}
      {section === "face_registration" && canApproveFace        && <div className="settings-card"><FaceRegistrationApprovalsTab /></div>}
      {section === "cancellations"     && canApproveLeave       && <LeaveCancellationsSection />}
      {section === "delegation"        && canDelegate           && <DelegationsSection />}
    </div>
  );
}
