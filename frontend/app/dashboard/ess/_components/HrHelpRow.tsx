"use client";

// One row of an HR Help list. Staff (canRespond) get a Respond button that opens the status / response form; everyone else
// sees a read-only row. Shared by the employee's own list (My Workspace > HR help) and the staff queue (Approvals > HR Requests).

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { HrHelpRequest } from "@/types/hrHelp";
import HrHelpChangePanel from "./HrHelpChangePanel";

const STATUS_BADGE: Record<string, string> = {
  open: "badge-warn", in_progress: "badge-info", resolved: "badge-success",
};

const fmtDateTime = (d: string) =>
  new Date(d).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

interface HrHelpRowProps {
  entry: HrHelpRequest;
  canRespond: boolean;
  onUpdated: () => void;
}

export default function HrHelpRow({ entry, canRespond, onUpdated }: HrHelpRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [status, setStatus] = useState(entry.status);
  const [response, setResponse] = useState(entry.response);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setErr(null);
    if (status === "resolved" && !response.trim()) {
      setErr("Enter a response explaining the resolution before marking this request resolved.");
      return;
    }
    setSaving(true);
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
        <td>
          <span className={`badge ${STATUS_BADGE[entry.status]}`}>{entry.status_display}</span>
          {entry.change_decision && <span className="badge badge-info" style={{ marginLeft: 6 }}>{entry.change_decision === "applied" ? "Updated" : "Declined"}</span>}
        </td>
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
              {entry.change_field && <HrHelpChangePanel entry={entry} note={response} onDecided={() => { onUpdated(); setExpanded(false); }} />}
              {err && <div className="alert alert-error" style={{ marginBottom: 10 }}>{err}</div>}
              <div className="field-group" style={{ marginBottom: 10, width: 180 }}>
                <label className="field-label">Status</label>
                <select className="field-input field-select" value={status} onChange={e => setStatus(e.target.value as HrHelpRequest["status"])}>
                  <option value="open">Open</option>
                  <option value="in_progress">In Progress</option>
                  <option value="resolved">Resolved</option>
                </select>
              </div>
              <div className="field-group" style={{ marginBottom: 10, maxWidth: 560 }}>
                <label className="field-label">
                  Response {status === "resolved" && <span style={{ color: "var(--error)" }}>*</span>}
                </label>
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
