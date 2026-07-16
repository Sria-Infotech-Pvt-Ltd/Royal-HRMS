"use client";

import Link from "next/link";
import { useActionItems } from "@/hooks/useEmployeeDashboard";
import type { ActionItem } from "@/types/employeeDashboard";

const ACTION_ICON: Record<string, { icon: string; color: string; bg: string }> = {
  profile_incomplete:   { icon: "ti-user-exclamation", color: "var(--error)",   bg: "rgba(220,38,38,0.10)"   },
  missing_document:     { icon: "ti-file-alert",       color: "var(--warn)",    bg: "rgba(217,119,6,0.10)"   },
  attendance_correction:{ icon: "ti-clock-exclamation",color: "var(--warn)",    bg: "rgba(217,119,6,0.10)"   },
  leave_approved:       { icon: "ti-circle-check",     color: "var(--success)", bg: "rgba(22,163,74,0.10)"   },
  leave_rejected:       { icon: "ti-circle-x",         color: "var(--error)",   bg: "rgba(220,38,38,0.10)"   },
};

const STATUS_BADGE: Record<string, string> = {
  pending:  "badge badge-warn",
  approved: "badge badge-success",
  rejected: "badge badge-error",
};

const STATUS_LABEL: Record<string, string> = {
  pending:  "Pending",
  approved: "Done",
  rejected: "Rejected",
};

const isDone = (item: ActionItem) =>
  item.status === "approved" || item.action_type === "leave_approved";

export default function EmpActionItems() {
  const { data, loading } = useActionItems();

  const items   = data?.action_items ?? [];
  const pending = items.filter(i => !isDone(i)).length;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clipboard-check" /> Action Items</div>
        {!loading && pending > 0 && <span className="badge badge-warn">{pending} pending</span>}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center" }}>
          <i className="ti ti-circle-check" style={{ fontSize: 26, color: "var(--success)", display: "block", marginBottom: 8, opacity: 0.6 }} />
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>All caught up!</div>
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {items.map((item, index) => {
            const meta  = ACTION_ICON[item.action_type] ?? { icon: "ti-info-circle", color: "var(--primary)", bg: "rgba(30,78,140,0.10)" };
            const done  = isDone(item);
            return (
              <Link
                key={index}
                href={item.navigation_url}
                style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "11px 20px", textDecoration: "none", opacity: done ? 0.6 : 1, borderBottom: "1px solid var(--border)" }}
              >
                <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: meta.bg, color: meta.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
                  <i className={`ti ${meta.icon}`} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: done ? 400 : 600, color: "var(--on-bg)", marginBottom: 2 }}>{item.title}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", lineHeight: 1.4 }}>{item.description}</div>
                </div>
                <span className={STATUS_BADGE[item.status] ?? "badge badge-neutral"} style={{ fontSize: 10, whiteSpace: "nowrap", marginTop: 2, flexShrink: 0 }}>
                  {STATUS_LABEL[item.status] ?? item.status}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
