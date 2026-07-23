"use client";

import { useRecentTeamActivity } from "@/hooks/useManagerDashboard";
import type { RecentActivityItem } from "@/types/managerDashboard";

const TYPE_META: Record<RecentActivityItem["type"], { dot: string; icon: string }> = {
  clock_in:      { dot: "tl-info",    icon: "ti-clock"  },
  leave_applied: { dot: "tl-warn",    icon: "ti-beach"  },
};

function timeAgo(iso: string): string {
  const date = new Date(iso);
  const now  = new Date();
  const sameDay = date.toDateString() === now.toDateString();
  const time = date.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" });
  if (sameDay) return `Today, ${time}`;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `Yesterday, ${time}`;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + `, ${time}`;
}

function describe(item: RecentActivityItem): string {
  if (item.type === "clock_in") return `${item.employee_name} clocked in`;
  const leaveType = ((item.details?.leave_type as string) ?? "").replace(/_/g, " ");
  return `${item.employee_name} applied for ${leaveType} leave`;
}

export default function ManagerRecentActivity() {
  const { data, loading } = useRecentTeamActivity();
  const items = data?.items ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-activity" /> Recent Team Activity</div>
      </div>
      <div className="card-body">
        {loading ? (
          <div style={{ padding: "10px 0", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
          </div>
        ) : items.length === 0 ? (
          <div style={{ padding: "10px 0", fontSize: 13, color: "var(--on-variant)" }}>
            No recent activity from your team.
          </div>
        ) : (
          <div className="timeline">
            {items.map((item, index) => {
              const meta = TYPE_META[item.type];
              return (
                <div key={index} className="tl-item">
                  <div className={`tl-dot ${meta.dot}`}><i className={`ti ${meta.icon}`} /></div>
                  <div className="tl-body">
                    <div className="tl-title">{describe(item)}</div>
                    <div className="tl-time">{timeAgo(item.created_at)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
