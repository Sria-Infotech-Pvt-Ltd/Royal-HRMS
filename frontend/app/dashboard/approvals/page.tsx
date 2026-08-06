"use client";

import { useEffect, useMemo, useState } from "react";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import TeamApprovalsSection from "./_components/TeamApprovalsSection";
import AttendanceApprovalTab from "./_components/AttendanceApprovalTab";
import FaceRegistrationApprovalsTab from "./_components/FaceRegistrationApprovalsTab";

type Section = "approvals" | "attendance" | "face_registration";

export default function ApprovalsPage() {
  const user = useCurrentUser();
  const [section, setSection] = useState<Section>("approvals");
  const canApprove      = useAnyPermission("leave.approve", "expenses.approve", "attendance.create");
  const canApproveFace  = usePermission("facial_recognition.approve");
  const hasPayrollView  = usePermission("payroll.view");
  // Managers, superusers, and anyone with payroll.view (payroll admins and HR
  // alike) get this tab — it's the only place attendance-cycle sign-off lives
  // now that Leave Management no longer has its own "Attendance Approvals" tab.
  const canApproveAttendance =
    user?.can_manage_team === true ||
    user?.is_superuser === true ||
    hasPayrollView;

  const sections: { key: Section; label: string; icon: string }[] = useMemo(() => [
    ...(canApprove           ? [{ key: "approvals"         as Section, label: "Team Approvals",      icon: "ti-checks"         }] : []),
    ...(canApproveAttendance ? [{ key: "attendance"         as Section, label: "Attendance Approval", icon: "ti-calendar-check" }] : []),
    ...(canApproveFace       ? [{ key: "face_registration"  as Section, label: "Face Registration",   icon: "ti-face-id"        }] : []),
  ], [canApprove, canApproveAttendance, canApproveFace]);

  useEffect(() => {
    if (sections.length > 0 && !sections.some(s => s.key === section)) {
      setSection(sections[0].key);
    }
  }, [section, sections]);

  return (
    <div>
      <div style={{ display: "flex", gap: 2, borderBottom: "2px solid var(--outline-v)", marginBottom: 24 }}>
        {sections.map(s => (
          <button
            key={s.key}
            suppressHydrationWarning
            onClick={() => setSection(s.key)}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "10px 20px", fontSize: 13,
              fontWeight: section === s.key ? 600 : 400,
              color: section === s.key ? "var(--primary)" : "var(--on-variant)",
              background: "none", border: "none", cursor: "pointer",
              borderBottom: section === s.key ? "2px solid var(--primary)" : "2px solid transparent",
              marginBottom: -2, transition: "all 0.12s",
            }}
          >
            <i className={`ti ${s.icon}`} style={{ fontSize: 16 }} />
            {s.label}
          </button>
        ))}
      </div>

      {section === "approvals"         && canApprove           && <TeamApprovalsSection />}
      {section === "attendance"        && canApproveAttendance && <div className="settings-card"><AttendanceApprovalTab /></div>}
      {section === "face_registration" && canApproveFace        && <div className="settings-card"><FaceRegistrationApprovalsTab /></div>}
    </div>
  );
}
