"use client";

// Per-employee Audit Trail — reuses the existing /settings/audit/ endpoint
// (same one Settings > Audit Log uses) filtered by this employee's UUID via
// its new `object_id` query param, rather than building a separate audit
// surface. Read-only, same "supplementary — a failed fetch just leaves the
// table empty" convention as PromotionTab's own history fetch.

import { useCallback, useEffect, useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDateTime } from "@/lib/formatDate";

interface Props {
  employeeUuid: string;
}

interface ApiAuditLogEntry {
  id: number;
  actor_name: string;
  actor_email: string;
  actor_role: string;
  action: string;
  module: string;
  object_id: string;
  ip_address: string | null;
  created_at: string;
}

const fmtDateTime = (d: string) => formatDateTime(d);

const actionLabel = (action: string) =>
  action.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

export default function AuditTrailTab({ employeeUuid }: Props) {
  const canView = usePermission("audit.view");

  const [entries, setEntries] = useState<ApiAuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async () => {
    if (!employeeUuid || !canView) { setLoading(false); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await clientApi.get(API.settings.audit, { params: { object_id: employeeUuid, page_size: 50 } });
      setEntries(res.data?.data?.results ?? []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to load audit trail.");
    } finally {
      setLoading(false);
    }
  }, [employeeUuid, canView]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  if (!canView) {
    return (
      <div className="empty-state">
        <i className="ti ti-lock" />
        <h3>No permission</h3>
        <p>You do not have permission to view the audit trail.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-history" /> Audit Trail</div>
      </div>

      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}

      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading audit trail…</h3>
        </div>
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-history" />
          <h3>No audit events yet</h3>
          <p>Changes made to this employee&apos;s record will be listed here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Action</th>
                <th>By</th>
                <th>Module</th>
                <th>When</th>
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.id}>
                  <td style={{ fontWeight: 600 }}>{actionLabel(e.action)}</td>
                  <td>{e.actor_name || e.actor_email || "—"}</td>
                  <td style={{ color: "var(--on-variant)" }}>{e.module}</td>
                  <td style={{ color: "var(--on-variant)" }}>{fmtDateTime(e.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
