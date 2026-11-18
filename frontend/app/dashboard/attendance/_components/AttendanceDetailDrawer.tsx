"use client";

// The panel that opens from a day in the attendance table or the month calendar: who and which day with the status in colour, the four
// times, plain-words banners for anything unusual, and Punches / Corrections / History tabs. The pieces are the Detail*.tsx files here.

import { useRef, useState } from "react";
import { useAttendanceDetail } from "@/hooks/useAttendanceDetail";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { CorrectionReviewAction } from "@/types/attendance";
import { AttendanceEditForm } from "./AttendanceEditForm";
import DetailAuditTimeline from "./DetailAuditTimeline";
import DetailBanners from "./DetailBanners";
import DetailCorrections from "./DetailCorrections";
import DetailHeader from "./DetailHeader";
import DetailPunchTimeline from "./DetailPunchTimeline";
import DetailTabs from "./DetailTabs";
import DetailTimeTiles from "./DetailTimeTiles";
import { detailBanners } from "./detailView";
import { localISODate } from "./monthView";

interface Props {
  recordId:         string;
  date:             string;
  onClose:          () => void;
  onRecordChanged?: () => void;
}

export default function AttendanceDetailDrawer({ recordId, date, onClose, onRecordChanged }: Props) {
  const { showToast } = useToast();
  const canReview = usePermission("attendance.create");
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [editing, setEditing]         = useState(false);
  const [tab, setTab]                 = useState("punches");
  const [todayISO]                    = useState(() => localISODate());

  const { record, loading, error, refetch, corrections, refetchCorrections, auditEntries, auditLoading, auditError } = useAttendanceDetail(recordId, date);

  async function handleReview(correctionId: string, action: CorrectionReviewAction) {
    setReviewingId(correctionId);
    try {
      await clientApi.patch(API.attendance.correctionReview(correctionId), { action });
      showToast(action === "approve" ? "Correction approved. Attendance record updated." : "Correction rejected.", "success");
      refetchCorrections();
    } catch (err: unknown) {
      showToast((err as { message?: string })?.message ?? "Failed to review correction.", "error");
    } finally {
      setReviewingId(null);
    }
  }

  // A click's target is resolved at mouseup, not mousedown: selecting text inside the panel and releasing past its edge would otherwise
  // land on the overlay and close it. Only close when the gesture both started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="drawer-overlay open"
      onMouseDown={event => { mouseDownOnOverlay.current = event.target === event.currentTarget; }}
      onClick={event => { if (mouseDownOnOverlay.current && event.target === event.currentTarget) onClose(); }}
    >
      <div className="drawer open" onClick={event => event.stopPropagation()}>
        <div className="drawer-header">
          <span className="drawer-title">Attendance Detail</span>
          <button className="drawer-close" onClick={onClose} aria-label="Close"><i className="ti ti-x" /></button>
        </div>

        <div className="drawer-body">
          {loading && <p style={{ color: "var(--on-variant)", fontSize: 13 }}>Loading…</p>}
          {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}

          {record && (
            <>
              <DetailHeader data={record} date={date} todayISO={todayISO} editing={editing} onEdit={() => setEditing(true)} />

              {editing && (
                <div style={{ background: "var(--surface)", border: "1.5px solid var(--primary)", borderRadius: 12, padding: "14px 16px", marginBottom: 14 }}>
                  <div style={{ fontWeight: 700, fontSize: 12, color: "var(--primary)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 12 }}>
                    <i className="ti ti-edit" style={{ marginRight: 5 }} /> Edit Attendance
                  </div>
                  <AttendanceEditForm
                    recordId={recordId}
                    initialStatus={record.status_key}
                    initialClockIn={record.clock_in === "—" ? "" : record.clock_in}
                    initialClockOut={record.clock_out === "—" ? "" : record.clock_out}
                    initialNote={record.note ?? ""}
                    onSaved={() => { setEditing(false); refetch(); onRecordChanged?.(); }}
                    onCancel={() => setEditing(false)}
                  />
                </div>
              )}

              <DetailBanners banners={detailBanners(record)} note={record.note} />
              <DetailTimeTiles clockIn={record.clock_in} clockOut={record.clock_out} totalHours={record.total_hours} overtime={record.overtime} />

              <DetailTabs
                active={tab} onChange={setTab}
                tabs={[
                  { id: "punches", label: "Punches", count: record.punches.length },
                  { id: "corrections", label: "Corrections", count: corrections.length },
                  { id: "history", label: "History", count: auditEntries.length },
                ]}
              />
              {tab === "punches" && <DetailPunchTimeline punches={record.punches} />}
              {tab === "corrections" && <DetailCorrections corrections={corrections} canReview={canReview} reviewingId={reviewingId} onReview={handleReview} />}
              {tab === "history" && <DetailAuditTimeline entries={auditEntries} loading={auditLoading} error={auditError} />}
            </>
          )}
        </div>

        <div className="drawer-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
