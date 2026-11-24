"use client";

// The side panel for marking attendance on a day that has no record. Its form is the existing AttendanceCreateForm.

import { useRef } from "react";
import { useT } from "@/hooks/useI18n";
import { AttendanceCreateForm } from "./AttendanceEditForm";
import type { EmployeeOption } from "./monthView";

interface Props {
  employee: EmployeeOption;
  date: string;
  onClose: () => void;
  onSaved: () => void;
}

export default function MarkAttendanceDrawer({ employee, date, onClose, onSaved }: Props) {
  // A click's target is resolved at mouseup, not mousedown, so selecting text inside the panel and releasing past its edge would land on
  // the backdrop and close it. Only close when the gesture both started AND ended on the backdrop itself.
  const t = useT();
  const mouseDownOnOverlay = useRef(false);
  return (
    <div
      className="drawer-overlay open"
      onMouseDown={event => { mouseDownOnOverlay.current = event.target === event.currentTarget; }}
      onClick={event => { if (mouseDownOnOverlay.current && event.target === event.currentTarget) onClose(); }}
    >
      <div className="drawer open" style={{ maxWidth: 420 }} onClick={event => event.stopPropagation()}>
        <div className="drawer-header">
          <span className="drawer-title">{t("Mark Attendance — {date}", { date })}</span>
          <button className="drawer-close" onClick={onClose} aria-label={t("Close")}><i className="ti ti-x" /></button>
        </div>
        <div className="drawer-body">
          <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>
            <i className="ti ti-user" style={{ marginRight: 6 }} />
            {employee.full_name} · {employee.employee_id}
          </div>
          <AttendanceCreateForm employeeId={employee.id} date={date} onSaved={onSaved} onCancel={onClose} />
        </div>
      </div>
    </div>
  );
}
