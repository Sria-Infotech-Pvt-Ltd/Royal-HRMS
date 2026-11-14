"use client";

// The Attendance tab's "Attendance requests" card: corrections and work-from-home requests. Each row opens its own detail
// dialog (a WFH one is where a pending request can be cancelled).

import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { MyCorrectionRequest } from "../../my-requests/_data";
import type { AttendanceRequestRow } from "./attendanceRequestRows";

interface AttendanceRequestsCardProps {
  rows: AttendanceRequestRow[];
  onOpenCorrection: (request: MyCorrectionRequest) => void;
  onOpenWfh: (request: WorkFromHomeRequest) => void;
  /** The card shows only the newest few; this goes to the full list (the Requests tab). */
  onViewAll?: () => void;
}

export default function AttendanceRequestsCard({ rows, onOpenCorrection, onOpenWfh, onViewAll }: AttendanceRequestsCardProps) {
  return (
    <div className="ess-card">
      <h2>Attendance requests</h2>
      <p>Corrections and work-from-home requests, newest first.</p>
      <div className="ess-list">
        {rows.length === 0 && (
          <div className="ess-row">
            <div>
              <b>No attendance requests yet</b>
              <small>Use Regularize attendance if a punch was missed or recorded incorrectly, or Request work from home to work remotely.</small>
            </div>
          </div>
        )}
        {rows.map(row => {
          const { correction, wfh } = row;
          return (
            <button
              key={row.key} className="ess-row ess-row-link" type="button"
              onClick={() => { if (correction) onOpenCorrection(correction); else if (wfh) onOpenWfh(wfh); }}
            >
              <div><b>{row.title}</b><small>{row.detail}</small></div>
              <span className={`state${row.isApproved ? " ok" : ""}`}>{row.statusLabel}</span>
            </button>
          );
        })}
        {onViewAll && rows.length > 0 && (
          <button className="ess-row ess-row-link" type="button" onClick={onViewAll}>
            <div><b>View all requests</b><small>Every leave, expense, attendance, work-from-home and HR help request</small></div>
            <span className="row-go" aria-hidden="true">›</span>
          </button>
        )}
      </div>
    </div>
  );
}
