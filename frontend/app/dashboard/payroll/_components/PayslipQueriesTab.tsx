"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import type { PayslipQuery } from "@/types/payroll";
import ResolveQueryModal from "./ResolveQueryModal";

const fmtDate = (s: string) => new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

export default function PayslipQueriesTab() {
  const canEdit = usePermission("payroll.edit");
  const { data: queries, loading, refetch } = useFetch<PayslipQuery[]>(API.payroll.queries);
  const [resolveTarget, setResolveTarget] = useState<PayslipQuery | null>(null);
  const [saveMsg, setSaveMsg] = useState("");

  const rows = queries ?? [];

  return (
    <div style={{ marginTop: 24 }}>
      {saveMsg && (
        <div className="alert alert-success" style={{ marginBottom: 16 }}>
          {saveMsg}
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 12 }} onClick={() => setSaveMsg("")}>Dismiss</button>
        </div>
      )}

      {loading ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>
      ) : rows.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)", border: "1.5px dashed var(--outline-v)", borderRadius: "var(--radius)" }}>
          <i className="ti ti-message-circle" style={{ fontSize: 32, display: "block", marginBottom: 8 }} />
          No open payslip queries.
        </div>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Query</th>
                <th>Raised</th>
                <th>Status</th>
                {canEdit && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {rows.map(q => (
                <tr key={q.id}>
                  <td>{q.raised_by_name}</td>
                  <td style={{ maxWidth: 420 }}>{q.description}</td>
                  <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtDate(q.created_at)}</td>
                  <td><span className="badge badge-warn">Open</span></td>
                  {canEdit && (
                    <td>
                      <button className="btn btn-filled btn-sm" onClick={() => setResolveTarget(q)}>
                        <i className="ti ti-check" /> Resolve
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {resolveTarget && (
        <ResolveQueryModal
          query={resolveTarget}
          onClose={() => setResolveTarget(null)}
          onResolved={() => {
            setResolveTarget(null);
            setSaveMsg("Query resolved.");
            refetch();
          }}
        />
      )}
    </div>
  );
}
