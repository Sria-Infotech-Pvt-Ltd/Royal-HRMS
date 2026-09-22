"use client";

import { useRouter } from "next/navigation";
import { useRef } from "react";
import { fullName, initials, avatarColor, type Employee } from "../_data";
import Avatar from "./Avatar";
import EmployeeFullRecordBody from "./EmployeeFullRecordBody";

interface Props {
  employee: Employee;
  onClose:  () => void;
  /** "self" hides the admin-only "Edit full record"/reveal-sensitive controls — used by the ESS "Open full employee profile" view. */
  mode?: "admin" | "self";
  /** Self mode only: routes to the profile-correction request flow (ESS "My Profile" → edit form). Falls back to /dashboard/profile when omitted. */
  onRequestCorrection?: () => void;
  /** Self mode only: overrides the correction button's label — e.g. "Edit my record" for
      an admin/HR user editing their own record directly instead of filing a request. */
  correctionLabel?: string;
}

export default function EmployeeDrawer({ employee, onClose, mode = "admin", onRequestCorrection, correctionLabel }: Props) {
  const router = useRouter();
  const isAdmin = mode === "admin";
  const isSelf  = mode === "self";
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="drawer-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="drawer open" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Avatar text={initials(employee.firstName, employee.lastName)} size={32} color={avatarColor(employee.department)} photoUrl={employee.photoUrl} />
            <div>
              <div className="drawer-title">{fullName(employee)}</div>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{employee.code} · {employee.designation || "—"}</span>
            </div>
          </div>
          <button className="drawer-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="drawer-body">
          <EmployeeFullRecordBody employee={employee} mode={mode} />
        </div>

        <div className="drawer-footer" style={{ flexDirection: "column", alignItems: "stretch", gap: 10 }}>
          {isSelf && (
            <div style={{ display: "flex", gap: 10 }}>
              <button className="btn btn-filled" onClick={onRequestCorrection ?? (() => router.push("/dashboard/profile"))}>
                {correctionLabel ?? "Request profile correction"}
              </button>
              <button className="btn btn-outline" onClick={() => router.push("/dashboard/leave")}>Request leave</button>
            </div>
          )}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
            {isAdmin && (
              <button className="btn btn-filled" onClick={() => router.push(`/dashboard/employees/${employee.id}`)}>
                Edit full record
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
