"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { fullName, initials, avatarColor, type Employee } from "../_data";
import Avatar from "./Avatar";
import EmployeeFullRecordBody from "./EmployeeFullRecordBody";
import EditRecordModal from "./EditRecordModal";
import { usePermission } from "@/hooks/usePermission";
import ViewWorkspaceButton from "@/components/employees/ViewWorkspaceButton";

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
  // Full-record editing uses the sectioned edit modal; the detail page remains
  // available separately for read-only profile tabs and history.
  const canEditRecord = usePermission("employees.edit");
  const mouseDownOnOverlay = useRef(false);
  const [editOpen, setEditOpen] = useState(false);

  return (
    <div
      className="drawer-overlay open"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onClose(); }}
    >
      <div className="drawer open emp-drawer" onClick={e => e.stopPropagation()}>
        <div className="dh">
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <Avatar
              text={initials(employee.firstName, employee.lastName)} size={40} radius={12}
              color={avatarColor(employee.department)} photoUrl={employee.photoUrl}
            />
            <div style={{ minWidth: 0 }}>
              <div className="n">{fullName(employee)}</div>
              <div className="i">{employee.code} · {employee.designation || "—"}</div>
            </div>
          </div>
          <button className="xbtn" onClick={onClose} aria-label="Close">
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="dbody">
          <EmployeeFullRecordBody employee={employee} mode={mode} />
        </div>

        <div className="dfoot">
          <button className="rvbtn ghost" onClick={onClose}>Close</button>
          <span className="spacer" />
          {isSelf && (
            <>
              <button className="rvbtn" onClick={() => router.push("/dashboard/leave")}>Request leave</button>
              <button className="rvbtn pri" onClick={onRequestCorrection ?? (() => router.push("/dashboard/profile"))}>
                {correctionLabel ?? "Request profile correction"}
              </button>
            </>
          )}
          {isAdmin && <ViewWorkspaceButton employeeUuid={employee.uuid} className="rvbtn" />}
          {isAdmin && canEditRecord && (
            <button className="rvbtn pri" onClick={() => setEditOpen(true)}>
              Edit full record
            </button>
          )}
        </div>
      </div>

      {editOpen && <EditRecordModal employee={employee} onClose={() => setEditOpen(false)} />}
    </div>
  );
}
