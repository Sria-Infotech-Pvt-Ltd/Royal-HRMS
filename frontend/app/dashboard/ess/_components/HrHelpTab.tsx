"use client";

// HR Help — self-service support requests: submit a request and follow your own. The staff queue (every employee's requests,
// with the status / response actions) lives on the Approvals page, under HR Requests — see approvals/_components/HrRequestsTab.tsx.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { HrHelpRequest } from "@/types/hrHelp";
import HrHelpRow from "./HrHelpRow";

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
export default function HrHelpTab() {
  // mine=1: only this person's own tickets, even for staff who can see everyone's (that queue is on the Approvals page).
  const { data: page, loading, error, refetch } = useFetch<PagedResponse<HrHelpRequest>>(`${API.hrHelp.list}?page_size=100&mine=1`);
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

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start", flexWrap: "wrap", marginBottom: 20 }}>
        <div className="card" style={{ flex: "0 1 600px" }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-headset" /> Create HR request</div>
          </div>
          <div style={{ padding: "20px 24px" }}>
            {submitErr && <div className="alert alert-error" style={{ marginBottom: 16 }}>{submitErr}</div>}
            <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" }}>
              <div className="field-group" style={{ flex: "0 1 220px", minWidth: 0 }}>
                <label className="field-label">Topic</label>
                <select className="field-input field-select" value={topic} onChange={e => setTopic(e.target.value)}>
                  {TOPICS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="field-group" style={{ flex: "0 1 160px", minWidth: 0 }}>
                <label className="field-label">Priority</label>
                <select className="field-input field-select" value={priority} onChange={e => setPriority(e.target.value)}>
                  {PRIORITIES.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                </select>
              </div>
            </div>
            <div className="field-group" style={{ marginBottom: 16, maxWidth: 560 }}>
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

        <SupportStatusCard openCount={requests.filter(r => r.status !== "resolved").length} />
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-list-details" /> My HR requests</div>
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
                  <th>Topic</th>
                  <th>Priority</th>
                  <th>Status</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(r => (
                  <HrHelpRow key={r.id} entry={r} canRespond={false} onUpdated={refetch} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function SupportStatusCard({ openCount }: { openCount: number }) {
  return (
    <div className="card" style={{ flex: "1 1 240px", minWidth: "min(240px, 100%)" }}>
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
