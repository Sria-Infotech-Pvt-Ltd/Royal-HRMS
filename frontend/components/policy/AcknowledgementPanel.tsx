"use client";

// Company Policy acknowledgement inside the Document Center detail popup.
// Employees confirm they have read and accept the current version; HR
// (documents.edit) can switch acknowledgement on and see who has / hasn't.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { ackState, filterAckRows, type AckFields, type AckReportRow } from "@/lib/policyAck";

interface Props {
  doc: AckFields & { id: number; title: string };
  canManage: boolean;
  onChanged: (patch: Partial<AckFields>) => void;
}

interface AckReport {
  document: { id: number; title: string; version: number };
  total: number;
  acknowledged: number;
  employees: AckReportRow[];
}

function fmt(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "";
}

export default function AcknowledgementPanel({ doc, canManage, onChanged }: Props) {
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy]         = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [report, setReport]     = useState<AckReport | null>(null);
  const [show, setShow]         = useState<"all" | "pending" | "acknowledged">("pending");
  const state = ackState(doc);

  async function acknowledge() {
    setBusy(true); setError(null);
    try {
      const res = await clientApi.post<{ data: { acknowledged_at: string } }>(
        API.companyPolicy.acknowledge(doc.id), { version: doc.version },
      );
      onChanged({ my_acknowledged_at: res.data.data.acknowledged_at });
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Could not record your acknowledgement.");
    } finally { setBusy(false); }
  }

  async function requireAck(value: boolean) {
    setBusy(true); setError(null);
    try {
      await clientApi.patch(`/documents/${doc.id}/`, { requires_acknowledgement: value });
      onChanged({ requires_acknowledgement: value, my_acknowledged_at: null });
      setReport(null);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Could not update the document.");
    } finally { setBusy(false); }
  }

  async function loadReport() {
    setBusy(true); setError(null);
    try {
      const res = await clientApi.get<{ data: AckReport }>(API.companyPolicy.acknowledgements(doc.id));
      setReport(res.data.data);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Could not load acknowledgements.");
    } finally { setBusy(false); }
  }

  if (state === "not_required" && !canManage) return null;

  return (
    <div style={{ marginTop: 16, padding: 14, border: "1px solid var(--outline-v)", borderRadius: "var(--radius)" }}>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
        <i className="ti ti-signature" /> Acknowledgement
        {doc.requires_acknowledgement && <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>· version {doc.version}</span>}
      </div>

      {state === "acknowledged" && (
        <div style={{ fontSize: 13, color: "var(--success)" }}>
          <i className="ti ti-circle-check" /> You acknowledged this version on {fmt(doc.my_acknowledged_at)}.
        </div>
      )}

      {state === "pending" && (
        <>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 8 }}>
            Please open and read this document, then confirm below.
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, marginBottom: 10 }}>
            <input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} />
            I have read this document and accept the guidelines in it.
          </label>
          <button className="btn btn-filled btn-sm" disabled={!accepted || busy} onClick={acknowledge}>
            <i className="ti ti-check" /> Acknowledge
          </button>
        </>
      )}

      {canManage && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 12 }}>
          {doc.requires_acknowledgement ? (
            <>
              <button className="btn btn-outline btn-sm" disabled={busy} onClick={loadReport}>
                <i className="ti ti-users" /> View acknowledgements
              </button>
              <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => requireAck(false)}>
                Stop asking for acknowledgement
              </button>
            </>
          ) : (
            <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => requireAck(true)}>
              <i className="ti ti-signature" /> Require employees to acknowledge
            </button>
          )}
        </div>
      )}

      {error && <div className="field-error" role="alert" style={{ marginTop: 8 }}>{error}</div>}

      {report && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, fontSize: 12.5 }}>
            <strong>{report.acknowledged} of {report.total}</strong> acknowledged version {report.document.version}
            <select className="field-input" style={{ width: 150, marginLeft: "auto" }} value={show}
              onChange={e => setShow(e.target.value as typeof show)} aria-label="Show">
              <option value="pending">Not yet</option>
              <option value="acknowledged">Acknowledged</option>
              <option value="all">Everyone</option>
            </select>
          </div>
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            <table style={{ width: "100%", fontSize: 12 }}>
              <thead><tr><th style={{ textAlign: "left" }}>Employee</th><th style={{ textAlign: "left" }}>Branch</th><th style={{ textAlign: "left" }}>Acknowledged</th></tr></thead>
              <tbody>
                {filterAckRows(report.employees, show).map(r => (
                  <tr key={r.employee_id}>
                    <td>{r.name} <span style={{ color: "var(--outline)" }}>{r.employee_id}</span></td>
                    <td>{r.branch}</td>
                    <td>{r.acknowledged_at ? fmt(r.acknowledged_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
