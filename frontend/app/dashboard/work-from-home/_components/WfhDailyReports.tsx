"use client";

// WFH daily work report (company policy section 7): the employee submits what
// they completed, what's pending and any updates by end of day; their Senior /
// Department Head (or HR) marks it Full Day, Half Day or Not accepted.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { REVIEW_LABEL, reportFormError, reviewError, type ReviewStatus, type WfhDailyReport } from "@/lib/wfhReport";

function todayISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const BADGE: Record<ReviewStatus, string> = {
  pending: "badge badge-warn", full_day: "badge badge-success", half_day: "badge badge-primary", not_accepted: "badge badge-error",
};

function errMsg(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
    ?? (err as { message?: string })?.message ?? fallback;
}

export default function WfhDailyReports() {
  const mine   = useFetch<WfhDailyReport[]>(`${API.workFromHome.reports}?mine=1`);
  const review = useFetch<WfhDailyReport[]>(API.workFromHome.reports);

  const [date, setDate]           = useState(todayISO());
  const [completed, setCompleted] = useState("");
  const [pending, setPending]     = useState("");
  const [updates, setUpdates]     = useState("");
  const [busy, setBusy]           = useState(false);
  const [message, setMessage]     = useState<{ ok: boolean; text: string } | null>(null);

  async function submit() {
    const problem = reportFormError(completed);
    if (problem) { setMessage({ ok: false, text: problem }); return; }
    setBusy(true); setMessage(null);
    try {
      await clientApi.post(API.workFromHome.reports, { date, completed_work: completed, pending_work: pending, updates });
      setMessage({ ok: true, text: "Report submitted." });
      setCompleted(""); setPending(""); setUpdates("");
      mine.refetch();
    } catch (err: unknown) {
      setMessage({ ok: false, text: errMsg(err, "Could not submit the report.") });
    } finally { setBusy(false); }
  }

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div className="card">
        <div className="card-header"><div className="card-title"><i className="ti ti-report" /> Today&apos;s Work Report</div></div>
        <div className="card-body">
          <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 0 }}>
            Submit a report for every approved WFH day by end of day. A missing or late report may be marked Absent.
          </p>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Date</label>
              <input type="date" className="field-input" value={date} max={todayISO()} onChange={e => setDate(e.target.value)} />
            </div>
          </div>
          <div className="field-group">
            <label className="field-label">Work completed *</label>
            <textarea className="field-input" rows={3} value={completed} onChange={e => setCompleted(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label">Pending work</label>
            <textarea className="field-input" rows={2} value={pending} onChange={e => setPending(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label">Updates</label>
            <textarea className="field-input" rows={2} value={updates} onChange={e => setUpdates(e.target.value)} />
          </div>
          {message && <div className={`alert ${message.ok ? "alert-success" : "alert-error"} mb-16`} role="status">{message.text}</div>}
          <button className="btn btn-filled" onClick={submit} disabled={busy}>{busy ? "Submitting…" : "Submit Report"}</button>
        </div>
      </div>

      <ReportTable title="My Reports" rows={mine.data ?? []} />

      {(review.data ?? []).length > 0 && (
        <ReportTable title="Reports to Review" rows={review.data ?? []} showEmployee onReviewed={review.refetch} />
      )}
    </div>
  );
}

function ReportTable({ title, rows, showEmployee = false, onReviewed }: {
  title: string; rows: WfhDailyReport[]; showEmployee?: boolean; onReviewed?: () => void;
}) {
  return (
    <div className="card">
      <div className="card-header"><div className="card-title">{title}</div></div>
      {rows.length === 0 ? (
        <div className="card-body" style={{ color: "var(--on-variant)" }}>No reports yet.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{showEmployee && <th>Employee</th>}<th>Date</th><th>Work</th><th>Status</th>{showEmployee && <th />}</tr>
            </thead>
            <tbody>
              {rows.map(r => <ReportRow key={r.id} r={r} showEmployee={showEmployee} onReviewed={onReviewed} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ReportRow({ r, showEmployee, onReviewed }: { r: WfhDailyReport; showEmployee: boolean; onReviewed?: () => void }) {
  const [outcome, setOutcome] = useState<ReviewStatus | "">("");
  const [remarks, setRemarks] = useState("");
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState<string | null>(null);

  async function review() {
    const problem = reviewError(outcome, remarks);
    if (problem) { setError(problem); return; }
    setBusy(true); setError(null);
    try {
      await clientApi.post(API.workFromHome.reportReview(r.id), { outcome, remarks });
      onReviewed?.();
    } catch (err: unknown) {
      setError(errMsg(err, "Could not save the review."));
    } finally { setBusy(false); }
  }

  return (
    <tr>
      {showEmployee && <td>{r.employee_name} <span style={{ color: "var(--outline)" }}>{r.employee_code}</span></td>}
      <td style={{ whiteSpace: "nowrap" }}>{r.date}{r.submitted_late && <div style={{ fontSize: 11, color: "var(--error)" }}>Submitted late</div>}</td>
      <td style={{ fontSize: 12.5, maxWidth: 420 }}>
        <div><strong>Done:</strong> {r.completed_work}</div>
        {r.pending_work && <div><strong>Pending:</strong> {r.pending_work}</div>}
        {r.updates && <div><strong>Updates:</strong> {r.updates}</div>}
        {r.review_remarks && <div style={{ color: "var(--on-variant)" }}><strong>Reviewer:</strong> {r.review_remarks}</div>}
      </td>
      <td><span className={BADGE[r.review_status]}>{REVIEW_LABEL[r.review_status]}</span>
        {r.reviewed_by_name && <div style={{ fontSize: 11, color: "var(--outline)" }}>by {r.reviewed_by_name}</div>}</td>
      {showEmployee && (
        <td style={{ minWidth: 220 }}>
          {r.can_review && (
            <div style={{ display: "grid", gap: 6 }}>
              <select className="field-input" value={outcome} onChange={e => setOutcome(e.target.value as ReviewStatus | "")} aria-label="Outcome">
                <option value="">Choose outcome…</option>
                <option value="full_day">Full Day</option>
                <option value="half_day">Half Day</option>
                <option value="not_accepted">Not accepted</option>
              </select>
              <input className="field-input" placeholder="Remarks" value={remarks} onChange={e => setRemarks(e.target.value)} />
              <button className="btn btn-filled btn-sm" onClick={review} disabled={busy}>Save review</button>
              {error && <span className="field-error" role="alert">{error}</span>}
            </div>
          )}
        </td>
      )}
    </tr>
  );
}
