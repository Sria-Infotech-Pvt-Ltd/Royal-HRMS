"use client";

// The "<Cycle> goals" card on Growth — a read-only-styled list (bold title,
// "<description> · Due <date>", uppercase status pill) matching the
// reference mockup, plus the existing goal-creation/status/delete controls
// underneath. Goal creation has no other entry point in this app (no HR-side
// goal-setting screen exists yet — see performance/_client.tsx), so that
// working flow is kept, just moved below the read-only list rather than
// removed to chase the screenshot's exact framing.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import ConfirmModal from "@/components/ConfirmModal";

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

interface RowProps {
  goal: GrowthGoal;
  onStatusChange: (id: string, status: string) => void;
  onRemove: (goal: GrowthGoal) => void;
}

function GoalRow({ goal, onStatusChange, onRemove }: RowProps) {
  return (
    <div style={{ padding: "14px 0", borderBottom: "1px solid var(--outline-v)", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600 }}>{goal.title}</div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>
          {goal.description || goal.target_metric || "—"} · Due {goal.due_date ? formatDate(goal.due_date) : "—"}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span className={`badge ${STATUS_BADGE[goal.status]}`}>{STATUS_LABEL[goal.status]}</span>
        <select
          className="field-input field-select"
          style={{ padding: "3px 6px", fontSize: 11 }}
          value={goal.status}
          onChange={e => onStatusChange(goal.id, e.target.value)}
          title="Update status"
        >
          {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" onClick={() => onRemove(goal)} title="Remove goal">
          <i className="ti ti-trash" />
        </button>
      </div>
    </div>
  );
}

interface Props {
  cycleName: string | null;
  goals: GrowthGoal[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export default function GrowthGoalsCard({ cycleName, goals, loading, error, refetch }: Props) {
  const [title, setTitle] = useState("");
  const [targetMetric, setTargetMetric] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [adding, setAdding] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);
  const [rowErr, setRowErr] = useState<string | null>(null);
  const [removing, setRemoving] = useState<GrowthGoal | null>(null);
  const [removeSaving, setRemoveSaving] = useState(false);

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
  }

  async function handleAdd(): Promise<void> {
    setAddErr(null);
    setAdding(true);
    try {
      await clientApi.post(API.performance.myGoals, { title, target_metric: targetMetric, due_date: dueDate || null });
      setTitle(""); setTargetMetric(""); setDueDate("");
      refetch();
    } catch (err: unknown) {
      setAddErr(extractError(err, "Failed to add goal. Is there an active review cycle?"));
    } finally {
      setAdding(false);
    }
  }

  async function updateStatus(id: string, status: string): Promise<void> {
    setRowErr(null);
    try {
      await clientApi.patch(API.performance.myGoalDetail(id), { status });
      refetch();
    } catch (err: unknown) {
      setRowErr(extractError(err, "Failed to update goal status."));
    }
  }

  async function confirmRemove(): Promise<void> {
    if (!removing) return;
    setRemoveSaving(true);
    setRowErr(null);
    try {
      await clientApi.delete(API.performance.myGoalDetail(removing.id));
      setRemoving(null);
      refetch();
    } catch (err: unknown) {
      setRowErr(extractError(err, "Failed to remove goal."));
    } finally {
      setRemoveSaving(false);
    }
  }

  return (
    <div className="card mb-16">
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
        {rowErr && <div className="alert alert-error mb-16">{rowErr}</div>}
        {loading ? (
          <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading…</h3></div>
        ) : goals.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-target-arrow" />
            <h3>No goals yet</h3>
            <p>Add a goal below for the active review cycle.</p>
          </div>
        ) : (
          goals.map(g => (
            <GoalRow key={g.id} goal={g} onStatusChange={updateStatus} onRemove={setRemoving} />
          ))
        )}
      </div>

      {removing && (
        <ConfirmModal
          title="Remove this goal?"
          body={`This permanently removes "${removing.title}" from ${cycleName ?? "the active cycle"}.`}
          confirmLabel="Remove Goal"
          danger
          saving={removeSaving}
          onConfirm={confirmRemove}
          onCancel={() => setRemoving(null)}
        />
      )}

      <div style={{ padding: "16px 20px 20px", borderTop: "1px solid var(--outline-v)", marginTop: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--on-variant)", marginBottom: 10 }}>ADD A GOAL</div>
        {addErr && <div className="alert alert-error mb-16">{addErr}</div>}
        <div className="form-row cols-2" style={{ marginBottom: 12 }}>
          <div className="field-group">
            <label className="field-label">Title</label>
            <input className="field-input" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Improve platform reliability" />
          </div>
          <div className="field-group">
            <label className="field-label">Target</label>
            <input className="field-input" value={targetMetric} onChange={e => setTargetMetric(e.target.value)} placeholder="e.g. Reduce incidents by 20%" />
          </div>
          <div className="field-group">
            <label className="field-label">Due date</label>
            <input className="field-input" type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} />
          </div>
        </div>
        <button className="btn btn-filled" onClick={handleAdd} disabled={adding || !title.trim()}>
          {adding ? "Adding…" : "Add goal"}
        </button>
      </div>
    </div>
  );
}
