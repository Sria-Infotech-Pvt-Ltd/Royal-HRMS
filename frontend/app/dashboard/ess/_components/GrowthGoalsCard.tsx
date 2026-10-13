"use client";

// The "<Cycle> goals" card on Growth — a plain read-only list (bold title,
// "<description> · Due <date>", uppercase status pill), matching the
// reference layout exactly: no status-change control, no remove button, no
// inline "add a goal" form. Goal creation/editing has no self-service UI —
// see performance/_client.tsx for the HR-side goal-setting surface.

import { formatDate } from "@/lib/formatDate";

export interface GrowthGoal {
  id: string;
  title: string;
  description: string;
  target_metric: string;
  due_date: string | null;
  status: "on_track" | "at_risk" | "completed";
}

const STATUS_LABEL: Record<string, string> = { on_track: "ON TRACK", at_risk: "AT RISK", completed: "COMPLETED" };
const STATUS_BADGE: Record<string, string> = { on_track: "badge-success", at_risk: "badge-warn", completed: "badge-info" };

function GoalRow({ goal, isLast }: { goal: GrowthGoal; isLast: boolean }) {
  return (
    <div style={{ padding: "14px 0", borderBottom: isLast ? "none" : "1px solid var(--outline-v)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>{goal.title}</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
          {goal.description || goal.target_metric || "—"} · Due {goal.due_date ? formatDate(goal.due_date) : "—"}
        </div>
      </div>
      <span className={`badge ${STATUS_BADGE[goal.status]}`}>{STATUS_LABEL[goal.status]}</span>
    </div>
  );
}

interface Props {
  cycleName: string | null;
  goals: GrowthGoal[];
  loading: boolean;
  error: string | null;
}

export default function GrowthGoalsCard({ cycleName, goals, loading, error }: Props) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-target-arrow" /> {cycleName ? `${cycleName} goals` : "Goals"}</div>
      </div>
      <div style={{ padding: "4px 20px 0" }}>
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)" }}>
          Current goals are read-only until the review cycle opens for edits.
        </p>
      </div>

      <div style={{ padding: "8px 20px 4px" }}>
        {error && <div className="alert alert-error mb-16">{error}</div>}
        {loading ? (
          <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading…</h3></div>
        ) : goals.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-target-arrow" />
            <h3>No goals yet</h3>
            <p>Goals will appear here once the active review cycle sets them.</p>
          </div>
        ) : (
          goals.map((g, idx) => (
            <GoalRow key={g.id} goal={g} isLast={idx === goals.length - 1} />
          ))
        )}
      </div>
    </div>
  );
}
