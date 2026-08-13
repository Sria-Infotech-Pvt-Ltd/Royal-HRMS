"use client";

import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { SeparationActivityItem, SeparationRequest } from "@/types/separation";
import { fmtDateTime } from "../../_workflow";

const ROLE_GROUPS: { role: string; label: string; icon: string }[] = [
  { role: "employee", label: "Employee", icon: "ti-user" },
  { role: "manager",  label: "Manager",  icon: "ti-users" },
  { role: "hr_admin", label: "HR",       icon: "ti-briefcase" },
];

function groupByRole(activities: SeparationActivityItem[]) {
  const known = new Set(ROLE_GROUPS.map(g => g.role));
  const groups = ROLE_GROUPS.map(g => ({
    ...g,
    items: activities.filter(a => a.actor_role === g.role),
  }));
  const other = activities.filter(a => !known.has(a.actor_role));
  if (other.length > 0) groups.push({ role: "other", label: "Other", icon: "ti-settings", items: other });
  return groups;
}

function RoleGroup({ label, icon, items }: { label: string; icon: string; items: SeparationActivityItem[] }) {
  if (items.length === 0) return null;
  const rows = [...items].sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

  return (
    <div>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
        <i className={`ti ${icon}`} /> {label}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {rows.map(entry => (
          <div key={entry.id} style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
            <span style={{ fontSize: 13, color: "var(--on-bg)" }}>{entry.message}</span>
            <span style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
              {fmtDateTime(entry.created_at)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ActivitySection({ r }: { r: SeparationRequest }) {
  const { data: activities, loading } = useFetch<SeparationActivityItem[]>(API.separation.activities(r.id));
  const groups = groupByRole(activities ?? []);
  const hasAny = groups.some(g => g.items.length > 0);

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-history" /> Activity</span>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> Loading…</p>
        ) : !hasAny ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No activity recorded yet.</p>
        ) : (
          groups.map(g => <RoleGroup key={g.role} label={g.label} icon={g.icon} items={g.items} />)
        )}
      </div>
    </div>
  );
}
