"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { AttendanceAuditEntry, AttendanceDetail, CorrectionReviewAction, CorrectionStatus, PaginatedCorrections, PunchType } from "@/types/attendance";
import { AttendanceEditForm } from "./AttendanceEditForm";

interface Props {
  recordId:         string;
  date:             string;
  onClose:          () => void;
  onRecordChanged?: () => void;
}

const STATUS_BADGE: Record<string, string> = {
  present:    "badge badge-success",
  late:       "badge badge-warn",
  absent:     "badge badge-error",
  on_leave:   "badge badge-info",
  half_day:   "badge badge-primary",
  weekly_off: "badge badge-neutral",
  holiday:    "badge badge-neutral",
};

const CORRECTION_STATUS_BADGE: Record<CorrectionStatus, string> = {
  pending:  "badge badge-warn",
  approved: "badge badge-success",
  rejected: "badge badge-error",
};

const PUNCH_TYPE_LABEL: Record<PunchType, string> = {
  IN:   "Clock In",
  OUT:  "Clock Out",
  BOTH: "Both IN & OUT",
};

const AUDIT_EVENT_BADGE: Record<string, string> = {
  CLOCK_IN:                "badge badge-success",
  CLOCK_OUT:               "badge badge-info",
  CORRECTION_REQUESTED:    "badge badge-warn",
  CORRECTION_APPROVED:     "badge badge-success",
  CORRECTION_REJECTED:     "badge badge-error",
  IMPORTED:                "badge badge-primary",
  EDITED:                  "badge badge-warn",
  RECALCULATED:            "badge badge-info",
  INVALID_PUNCH_ASSIGNED:  "badge badge-primary",
  INVALID_PUNCH_DISCARDED: "badge badge-error",
  INVALID_PUNCH_CONVERTED: "badge badge-success",
};

function formatEventLabel(event: string): string {
  return event
    .split("_")
    .map(word => word.charAt(0) + word.slice(1).toLowerCase())
    .join(" ");
}

function SectionTitle({ icon, title }: { icon: string; title: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", marginTop: 22, marginBottom: 10 }}>
      <i className={`ti ${icon}`} /> {title}
    </div>
  );
}

export default function AttendanceDetailDrawer({ recordId, date, onClose, onRecordChanged }: Props) {
  const { showToast } = useToast();
  const [reviewingId, setReviewingId] = useState<string | null>(null);
  const [editing,     setEditing]     = useState(false);

  const { data, loading, error, refetch } = useFetch<AttendanceDetail>(
    `${API.attendance.record(recordId)}?date=${date}`
  );

  const correctionsUrl = data
    ? `${API.attendance.corrections}?employee_id=${data.employee_id}&date=${date}`
    : null;
  const { data: correctionsData, refetch: refetchCorrections } = useFetch<PaginatedCorrections>(correctionsUrl);
  const corrections = (correctionsData?.results ?? []).filter(
    c => c.employee_id === data?.employee_id && c.date === date
  );

  const { data: auditData, loading: auditLoading, error: auditError } =
    useFetch<AttendanceAuditEntry[]>(API.attendance.recordAudit(recordId));
  const auditEntries = (auditData ?? [])
    .slice()
    .sort((a, b) => b.performed_at.localeCompare(a.performed_at));

  async function handleReview(correctionId: string, action: CorrectionReviewAction) {
    setReviewingId(correctionId);
    try {
      await clientApi.patch(API.attendance.correctionReview(correctionId), { action });
      showToast(action === "approve" ? "Correction approved. Attendance record updated." : "Correction rejected.", "success");
      refetchCorrections();
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to review correction.";
      showToast(message, "error");
    } finally {
      setReviewingId(null);
    }
  }

  return (
    <div className="drawer-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="drawer open" onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <span className="drawer-title">Attendance Detail</span>
          <button className="drawer-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="drawer-body">
          {loading && <p style={{ color: "var(--on-variant)", fontSize: 13 }}>Loading…</p>}
          {error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}

          {data && (
            <>
              {/* Employee details */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                <div>
                  <div style={{ fontWeight: 700, fontSize: 15 }}>{data.name}</div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                    {data.employee_id} · {data.department} · {data.branch}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={STATUS_BADGE[data.status_key] ?? "badge badge-neutral"}>{data.status}</span>
                  {!editing && (
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ padding: "3px 10px", fontSize: 11 }}
                      onClick={() => setEditing(true)}
                    >
                      <i className="ti ti-edit" /> Edit
                    </button>
                  )}
                </div>
              </div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: editing ? 16 : 0 }}>{date}</div>

              {/* Edit form */}
              {editing && (
                <div style={{ background: "var(--bg)", border: "1.5px solid var(--primary)", borderRadius: 10, padding: "14px 16px", marginTop: 12, marginBottom: 4 }}>
                  <div style={{ fontWeight: 700, fontSize: 12, color: "var(--primary)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: 12 }}>
                    <i className="ti ti-edit" style={{ marginRight: 5 }} /> Edit Attendance
                  </div>
                  <AttendanceEditForm
                    recordId={recordId}
                    initialStatus={data.status_key}
                    initialClockIn={data.clock_in === "—" ? "" : data.clock_in}
                    initialClockOut={data.clock_out === "—" ? "" : data.clock_out}
                    initialNote={data.note ?? ""}
                    onSaved={() => {
                      setEditing(false);
                      refetch();
                      onRecordChanged?.();
                    }}
                    onCancel={() => setEditing(false)}
                  />
                </div>
              )}

              {/* Attendance calculation */}
              <SectionTitle icon="ti-calculator" title="Attendance Calculation" />
              <div className="form-row cols-2" style={{ marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Clock In</div>
                  <div style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 13 }}>{data.clock_in}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Clock Out</div>
                  <div style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 13 }}>{data.clock_out}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Total Hours</div>
                  <div style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 13 }}>{data.total_hours}</div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Overtime</div>
                  <div style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 13 }}>{data.overtime}</div>
                </div>
              </div>

              {(data.is_late || data.is_early_exit) && (
                <div className="alert alert-warn mb-16">
                  <i className="ti ti-alert-triangle" />
                  <span>
                    {data.is_late && "Late arrival"}
                    {data.is_late && data.is_early_exit && " · "}
                    {data.is_early_exit && "Early exit"}
                  </span>
                </div>
              )}

              {data.note && (
                <div className="alert alert-info mb-16">
                  <i className="ti ti-note" /> <span>{data.note}</span>
                </div>
              )}

              {/* Punch history + location */}
              <SectionTitle icon="ti-map-pin" title="Punch History & Location" />
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {data.punches.map((p, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
                    <i
                      className={p.is_geofence ? "ti ti-circle-check" : p.is_geofence === false ? "ti ti-circle-x" : "ti ti-circle-dashed"}
                      style={{ color: p.is_geofence ? "var(--success)" : p.is_geofence === false ? "var(--error)" : "var(--on-variant)", fontSize: 16 }}
                      title={p.is_geofence === true ? "Inside geofence" : p.is_geofence === false ? "Outside geofence" : "Geofence N/A"}
                    />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>
                        {p.punch_type} <span style={{ fontFamily: "Menlo, Consolas, monospace", fontWeight: 400 }}>{p.time}</span>
                      </div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                        {p.source} · {p.mode}
                        {p.distance_m !== null && ` · ${p.distance_m.toFixed(0)}m from geofence`}
                      </div>
                    </div>
                  </div>
                ))}
                {data.punches.length === 0 && (
                  <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No punches recorded for this day.</p>
                )}
              </div>

              {/* Correction requests */}
              <SectionTitle icon="ti-file-description" title="Correction Requests" />
              {corrections.length === 0 && (
                <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No correction requests for this day.</p>
              )}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {corrections.map(c => (
                  <div key={c.id} style={{ padding: "10px 12px", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{PUNCH_TYPE_LABEL[c.punch_type]}</span>
                      <span className={CORRECTION_STATUS_BADGE[c.status]}>{c.status}</span>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 4 }}>
                      Requested In: {c.requested_in ?? "—"} · Requested Out: {c.requested_out ?? "—"}
                    </div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{c.reason}</div>

                    {c.status === "pending" ? (
                      <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 10px", fontSize: 11, color: "var(--success)" }}
                          disabled={reviewingId === c.id}
                          onClick={() => handleReview(c.id, "approve")}
                        >
                          <i className="ti ti-check" /> Approve
                        </button>
                        <button
                          className="btn btn-outline btn-sm"
                          style={{ padding: "3px 10px", fontSize: 11, color: "var(--error)" }}
                          disabled={reviewingId === c.id}
                          onClick={() => handleReview(c.id, "reject")}
                        >
                          <i className="ti ti-x" /> Reject
                        </button>
                      </div>
                    ) : (
                      (c.reviewed_by || c.reviewed_at) && (
                        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>
                          Reviewed by {c.reviewed_by ?? "—"}{c.reviewed_at ? ` on ${c.reviewed_at}` : ""}
                        </div>
                      )
                    )}
                  </div>
                ))}
              </div>

              {/* Audit log */}
              <SectionTitle icon="ti-history" title="Audit History" />
              {auditLoading && (
                <p style={{ fontSize: 12, color: "var(--on-variant)" }}>Loading audit history…</p>
              )}
              {auditError && (
                <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {auditError}</div>
              )}
              {!auditLoading && !auditError && auditEntries.length === 0 && (
                <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No audit history for this record yet.</p>
              )}
              {auditEntries.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {auditEntries.map((entry, idx) => (
                    <div key={idx} style={{ display: "flex", gap: 10 }}>
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: 10 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--primary)", marginTop: 4, flexShrink: 0 }} />
                        {idx < auditEntries.length - 1 && (
                          <div style={{ flex: 1, width: 1, background: "var(--outline-v)", marginTop: 2 }} />
                        )}
                      </div>
                      <div style={{ paddingBottom: 16, flex: 1 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span className={AUDIT_EVENT_BADGE[entry.event] ?? "badge badge-neutral"}>
                            {formatEventLabel(entry.event)}
                          </span>
                          <span style={{ fontSize: 12, fontWeight: 600 }}>{entry.performed_by}</span>
                        </div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 4 }}>
                          {entry.performed_at}
                        </div>
                        <div style={{ fontSize: 12 }}>{entry.action}</div>
                        {entry.old_value && entry.new_value && (
                          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                            {entry.old_value} <i className="ti ti-arrow-right" /> {entry.new_value}
                          </div>
                        )}
                        {entry.remarks && (
                          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2, fontStyle: "italic" }}>
                            &ldquo;{entry.remarks}&rdquo;
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
