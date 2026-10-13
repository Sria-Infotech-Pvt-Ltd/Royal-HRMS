"use client";

// Presentational-only "Audit Trail" section for EmployeeDrawer.tsx — the
// fetch (and the real AuditLog "profile_viewed_self" event it triggers on
// self-service views) lives in the parent, keyed to that same employee, so
// it isn't duplicated per render. Split out purely to keep
// EmployeeDrawer.tsx under this codebase's ~300-line guideline.

import { formatDateSlash, formatTimeHm } from "@/lib/formatDate";
import { Row, SectionCard } from "./EmployeeDrawerParts";

export interface AuditTrailRow {
  id: number;
  actor_name: string;
  actor_role: string | null;
  action: string;
  created_at: string;
}

interface Props {
  rows: AuditTrailRow[] | null;
  /** The endpoint refused this viewer (needs audit.view): say so instead of
      claiming nothing has been recorded. */
  forbidden?: boolean;
  /** Still fetching: do not claim "nothing recorded" before the answer is in. */
  loading?: boolean;
}

export default function EmployeeDrawerAuditTrail({ rows, forbidden = false, loading = false }: Props) {
  return (
    <SectionCard title="Audit Trail" list={forbidden}>
      {forbidden ? (
        <Row label="Visibility" value="Permission required" />
      ) : loading ? (
        <p className="hint">Loading…</p>
      ) : !rows || rows.length === 0 ? (
        <p className="hint">No access recorded yet in this session.</p>
      ) : (
        rows.map(row => (
          <div key={row.id} className="actrow">
            <span className="bar" />
            <div className="meta">
              <div className="t1">{row.action === "profile_viewed_self" ? "Record viewed" : row.action}</div>
              <div className="t2">
                {row.actor_name} · {row.action === "profile_viewed_self" ? "Employee (self-service)" : (row.actor_role || "Admin")}
              </div>
            </div>
            <div className="dates" style={{ textAlign: "right" }}>
              {formatDateSlash(row.created_at)}
              <div className="actdel">{formatTimeHm(row.created_at)}</div>
            </div>
          </div>
        ))
      )}
    </SectionCard>
  );
}
