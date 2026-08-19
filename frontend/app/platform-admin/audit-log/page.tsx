"use client";

import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { AuditLogListResponse } from "@/types/platformAdmin";

const ACTION_LABELS: Record<string, string> = {
  company_created:             "Company created",
  company_updated:             "Company updated",
  company_password_revealed:   "Password revealed",
  platform_admin_invited:      "Admin invited",
  platform_admin_deactivated:  "Admin deactivated",
  platform_admin_reactivated:  "Admin reactivated",
};

export default function AuditLogPage() {
  const { data, loading, error } = useFetch<AuditLogListResponse>(API.platformAdmin.auditLogs, platformAdminApi);
  const logs = data?.results ?? [];

  return (
    <div style={{ padding: "32px 24px" }}>
      <a href="/platform-admin/settings" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12.5, marginBottom: 12 }}>
        <i className="ti ti-arrow-left" /> Settings
      </a>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 24 }}>Audit Log</h1>

      <div className="card">
        <div className="card-body" style={{ padding: 0 }}>
          {loading ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Loading audit log…
            </div>
          ) : error ? (
            <div className="alert alert-warn" style={{ margin: 16 }}><i className="ti ti-alert-triangle" /><div>{error}</div></div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
              No platform-admin actions recorded yet.
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Admin</th>
                    <th>Action</th>
                    <th>Company</th>
                    <th>Details</th>
                    <th>IP</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id}>
                      <td style={{ whiteSpace: "nowrap" }}>{new Date(log.created_at).toLocaleString()}</td>
                      <td>{log.admin_email}</td>
                      <td><span className="badge badge-neutral">{ACTION_LABELS[log.action] ?? log.action}</span></td>
                      <td>{log.target_company_code || <span className="text-muted">—</span>}</td>
                      <td style={{ fontSize: 12, fontFamily: "monospace", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {Object.keys(log.changes).length > 0 ? JSON.stringify(log.changes) : ""}
                      </td>
                      <td className="text-muted" style={{ fontSize: 12 }}>{log.ip_address || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
