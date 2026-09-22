"use client";

// Presentational-only "Audit Trail" section for EmployeeDrawer.tsx — the
// fetch (and the real AuditLog "profile_viewed_self" event it triggers on
// self-service views) lives in the parent, keyed to that same employee, so
// it isn't duplicated per render. Split out purely to keep
// EmployeeDrawer.tsx under this codebase's ~300-line guideline.

import { formatDateTime } from "@/lib/formatDate";
import { SectionCard } from "./EmployeeDrawerParts";

export interface AuditTrailRow {
  id: number;
  actor_name: string;
  actor_role: string | null;
  action: string;
  created_at: string;
}

export default function EmployeeDrawerAuditTrail({ rows }: { rows: AuditTrailRow[] | null }) {
  return (
    <SectionCard icon="ti-eye" title="Audit Trail">
      {!rows || rows.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No audit events recorded yet.</p>
      ) : (
        rows.map(row => (
          <div key={row.id} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 700 }}>{row.action === "profile_viewed_self" ? "Record viewed" : row.action}</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                {row.actor_name} · {row.action === "profile_viewed_self" ? "Employee (self-service)" : (row.actor_role || "Admin")}
              </div>
            </div>
            <div style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
              {formatDateTime(row.created_at)}
            </div>
          </div>
        ))
      )}
    </SectionCard>
  );
}
