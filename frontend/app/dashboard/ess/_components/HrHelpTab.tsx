"use client";

// HR Help — self-service support requests. Every employee can submit a
// request and see their own; hr_help.respond holders (system_admin/hr_admin/
// branch_admin) additionally get a queue of every request with a status/
// response action, reusing the same list endpoint (GET /hr-help/requests/
// scopes itself server-side — see HRHelpRequestListCreateView.get).

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface ApiHrHelpRequest {
  id: string;
  request_ref: string;
  topic: string;
  topic_display: string;
  priority: string;
  priority_display: string;
  message: string;
  status: "open" | "in_progress" | "resolved";
  status_display: string;
  response: string;
  submitted_by_name: string;
  assigned_to_name: string;
  created_at: string;
}
interface PagedResponse<T> { results: T[]; count: number }

const TOPICS = [
  { value: "payroll_query",    label: "Payroll query" },
  { value: "leave_query",      label: "Leave query" },
  { value: "attendance_query", label: "Attendance query" },
  { value: "document_request", label: "Document request" },
  { value: "policy_question",  label: "Policy question" },
  { value: "other",            label: "Other" },
];
const PRIORITIES = [
  { value: "low", label: "Low" },
  { value: "normal", label: "Normal" },
  { value: "high", label: "High" },
];
const STATUS_BADGE: Record<string, string> = {
  open: "badge-warn", in_progress: "badge-info", resolved: "badge-success",
};

const fmtDateTime = (d: string) =>
  new Date(d).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

export default function HrHelpTab() {
  const canRespond = usePermission("hr_help.respond");
  const { data: page, loading, error, refetch } = useFetch<PagedResponse<ApiHrHelpRequest>>(`${API.hrHelp.list}?page_size=100`);
  const requests = page?.results ?? [];

  const [topic, setTopic] = useState("payroll_query");
  const [priority, setPriority] = useState("normal");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitErr, setSubmitErr] = useState<string | null>(null);

  async function handleSubmit() {
    setSubmitErr(null);
    setSubmitting(true);
    try {
      await clientApi.post(API.hrHelp.list, { topic, priority, message });
      setMessage("");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSubmitErr(msg ?? "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">HR Help</div>
          <div className="page-sub">Submit a request and track its status with HR.</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-headset" /> Create HR request</div>
        </div>
        <div style={{ padding: "20px 24px" }}>
          {submitErr && <div className="alert alert-error" style={{ marginBottom: 16 }}>{submitErr}</div>}
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Topic</label>
              <select className="field-input field-select" value={topic} onChange={e => setTopic(e.target.value)}>
                {TOPICS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Priority</label>
              <select className="field-input field-select" value={priority} onChange={e => setPriority(e.target.value)}>
                {PRIORITIES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
          </div>
          <div className="field-group" style={{ marginBottom: 16 }}>
            <label className="field-label">Message</label>
            <textarea
              className="field-input"
              rows={3}
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Describe your question or request"
            />
          </div>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={submitting || message.trim().length < 10}>
            {submitting ? "Submitting…" : "Submit to HR"}
          </button>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap" }}>
        <div className="card" style={{ flex: "2 1 480px" }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-list-details" /> {canRespond ? "HR request queue" : "My HR requests"}</div>
          </div>
          {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
          {loading ? (
            <div className="empty-state">
              <i className="ti ti-loader-2 spin" />
              <h3>Loading requests…</h3>
            </div>
          ) : requests.length === 0 ? (
            <div className="empty-state">
              <i className="ti ti-headset" />
              <h3>No active HR cases</h3>
              <p>Your submitted requests will be listed here.</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Ref</th>
                    {canRespond && <th>From</th>}
                    <th>Topic</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Submitted</th>
                    {canRespond && <th>Action</th>}
                  </tr>
                </thead>
                <tbody>
                  {requests.map(r => (
                    <HrHelpRow key={r.id} entry={r} canRespond={canRespond} onUpdated={refetch} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <SupportStatusCard openCount={requests.filter(r => r.status !== "resolved").length} />
      </div>
    </div>
  );
}

function SupportStatusCard({ openCount }: { openCount: number }) {
  return (
    <div className="card" style={{ flex: "1 1 240px", minWidth: 240 }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-shield-check" /> Support status</div>
      </div>
      <div style={{ padding: "16px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>Open requests</span>
          <span className={`badge ${openCount === 0 ? "badge-success" : "badge-warn"}`}>
            {openCount === 0 ? "Clear" : openCount}
          </span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>Typical response</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>1 day</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>Confidentiality</span>
          <span className="badge badge-info">PRIVATE</span>
        </div>
        <p style={{ margin: 0, fontSize: 12, color: "var(--on-variant)" }}>
          Restricted to assigned HR team.
        </p>
      </div>
    </div>
  );
}

function HrHelpRow({ entry, canRespond, onUpdated }: { entry: ApiHrHelpRequest; canRespond: boolean; onUpdated: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState(entry.status);
  const [response, setResponse] = useState(entry.response);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setErr(null);
    try {
      await clientApi.patch(API.hrHelp.detail(entry.id), { status, response });
      onUpdated();
      setExpanded(false);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(msg ?? "Failed to update request.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <tr>
        <td style={{ fontWeight: 600 }}>{entry.request_ref}</td>
        {canRespond && <td>{entry.submitted_by_name}</td>}
        <td>{entry.topic_display}</td>
        <td>{entry.priority_display}</td>
        <td><span className={`badge ${STATUS_BADGE[entry.status]}`}>{entry.status_display}</span></td>
        <td style={{ color: "var(--on-variant)" }}>{fmtDateTime(entry.created_at)}</td>
        {canRespond && (
          <td>
            <button className="btn btn-ghost btn-sm" onClick={() => setExpanded(v => !v)}>
              {expanded ? "Close" : "Respond"}
            </button>
          </td>
        )}
      </tr>
      {expanded && canRespond && (
        <tr>
          <td colSpan={7} style={{ background: "var(--bg-mid)" }}>
            <div style={{ padding: 14 }}>
              <p style={{ fontSize: 13, marginBottom: 10 }}>{entry.message}</p>
              {err && <div className="alert alert-error" style={{ marginBottom: 10 }}>{err}</div>}
              <div className="form-row cols-2" style={{ marginBottom: 10 }}>
                <div className="field-group">
                  <label className="field-label">Status</label>
                  <select className="field-input field-select" value={status} onChange={e => setStatus(e.target.value as ApiHrHelpRequest["status"])}>
                    <option value="open">Open</option>
                    <option value="in_progress">In Progress</option>
                    <option value="resolved">Resolved</option>
                  </select>
                </div>
              </div>
              <div className="field-group" style={{ marginBottom: 10 }}>
                <label className="field-label">Response</label>
                <textarea className="field-input" rows={2} value={response} onChange={e => setResponse(e.target.value)} />
              </div>
              <button className="btn btn-filled btn-sm" onClick={save} disabled={saving}>
                {saving ? "Saving…" : "Save"}
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
