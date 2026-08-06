"use client";

import { useRecentRequests } from "@/hooks/useEmployeeDashboard";
import type { RecentRequest } from "@/types/employeeDashboard";
import AssessmentLockedNotice from "./AssessmentLockedNotice";

const REQUEST_META: Record<RecentRequest["request_type"], { icon: string; color: string; bg: string; label: string }> = {
  leave:                { icon: "ti-beach",  color: "var(--success)", bg: "rgba(22,163,74,0.10)",  label: "Leave"       },
  expense:              { icon: "ti-receipt",color: "var(--warn)",    bg: "rgba(217,119,6,0.10)",  label: "Expense"     },
  attendance_correction:{ icon: "ti-clock",  color: "var(--info)",   bg: "rgba(14,124,134,0.10)", label: "Attendance"  },
};

const STATUS_BADGE: Record<string, string> = {
  pending:    "badge badge-warn",
  l2_pending: "badge badge-warn",
  approved:   "badge badge-success",
  rejected:   "badge badge-error",
  cancelled:  "badge badge-neutral",
};

const STATUS_LABEL: Record<string, string> = {
  pending:    "Pending",
  l2_pending: "L2 Pending",
  approved:   "Approved",
  rejected:   "Rejected",
  cancelled:  "Cancelled",
};

function fmtDate(iso: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function detailLine(req: RecentRequest): string {
  const d = req.details;
  if (req.request_type === "leave") {
    const start = d.start_date as string | undefined;
    const end   = d.end_date   as string | undefined;
    const days  = d.days       as number | undefined;
    if (start && end) return `${fmtDate(start)} – ${fmtDate(end)}${days ? ` · ${days}d` : ""}`;
  }
  if (req.request_type === "expense") {
    const amount   = d.amount   as number  | undefined;
    const category = d.category as string | undefined;
    return [category, amount ? `₹${amount.toLocaleString("en-IN")}` : ""].filter(Boolean).join(" · ");
  }
  if (req.request_type === "attendance_correction") {
    const date      = d.date       as string | undefined;
    const punchType = d.punch_type as string | undefined;
    return [date ? fmtDate(date) : "", punchType ? `${punchType} punch` : ""].filter(Boolean).join(" · ");
  }
  return "";
}

// Dashboard stays lightweight — this shows the latest 5 requests only
// (useRecentRequests defaults to page_size=5); the full, searchable history
// lives on the My Requests page.
export default function EmpRecentRequests() {
  const { data, loading, status } = useRecentRequests(1);

  const requests = data?.results ?? [];
  const pending  = requests.filter(r => r.status === "pending" || r.status === "l2_pending").length;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-inbox" /> Recent Activity</div>
        {!loading && pending > 0 && (
          <span className="badge badge-warn">{pending} pending</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : status === 403 ? (
        <AssessmentLockedNotice />
      ) : requests.length === 0 ? (
        <div style={{ padding: "24px 20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
          No requests yet. <a href="/dashboard/leave" style={{ color: "var(--primary)" }}>Apply leave</a>
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {requests.map((req, index) => {
            const meta   = REQUEST_META[req.request_type];
            const detail = detailLine(req);
            return (
              <div key={index} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 20px", borderBottom: "1px solid var(--border)" }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, flexShrink: 0, background: meta.bg, color: meta.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>
                  <i className={`ti ${meta.icon}`} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{req.title}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                    {detail && <span>{detail} · </span>}
                    <span>{fmtDate(req.applied_date)}</span>
                  </div>
                </div>
                <span className={STATUS_BADGE[req.status] ?? "badge badge-neutral"} style={{ fontSize: 10, whiteSpace: "nowrap", flexShrink: 0 }}>
                  {STATUS_LABEL[req.status] ?? req.status}
                </span>
              </div>
            );
          })}
        </div>
      )}

      <div style={{ padding: "10px 20px", borderTop: "1px solid var(--border)" }}>
        <a href="/dashboard/my-requests" style={{ fontSize: 12, color: "var(--primary)", fontWeight: 500, textDecoration: "none" }}>
          View All Requests <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
        </a>
      </div>
    </div>
  );
}
