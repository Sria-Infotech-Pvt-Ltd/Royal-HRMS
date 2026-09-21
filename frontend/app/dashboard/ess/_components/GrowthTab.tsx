"use client";

// Growth — goals for the active review cycle + a simple review timeline
// (self-review / manager-review due dates). Goals are plain CRUD, no
// approval workflow (see apps/performance/models.py:Goal's own docstring).

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface ApiGoal {
  id: string;
  title: string;
  description: string;
  target_metric: string;
  due_date: string | null;
  status: "on_track" | "at_risk" | "completed";
}
interface ApiReview {
  cycle_name: string;
  status: string;
  status_display: string;
  self_submitted_at: string | null;
  manager_submitted_at: string | null;
}

const STATUS_LABEL: Record<string, string> = { on_track: "On Track", at_risk: "At Risk", completed: "Completed" };
const STATUS_BADGE: Record<string, string> = { on_track: "badge-success", at_risk: "badge-warn", completed: "badge-info" };

export default function GrowthTab() {
  const { data: goals, loading, error, refetch } = useFetch<ApiGoal[]>(API.performance.myGoals);
  const { data: review } = useFetch<ApiReview>(API.performance.myReview);

  const [title, setTitle] = useState("");
  const [targetMetric, setTargetMetric] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [adding, setAdding] = useState(false);
  const [addErr, setAddErr] = useState<string | null>(null);

  async function handleAdd() {
    setAddErr(null);
    setAdding(true);
    try {
      await clientApi.post(API.performance.myGoals, { title, target_metric: targetMetric, due_date: dueDate || null });
      setTitle(""); setTargetMetric(""); setDueDate("");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setAddErr(msg ?? "Failed to add goal. Is there an active review cycle?");
    } finally {
      setAdding(false);
    }
  }

  async function updateStatus(id: string, status: string) {
    await clientApi.patch(API.performance.myGoalDetail(id), { status });
    refetch();
  }

  async function remove(id: string) {
    await clientApi.delete(API.performance.myGoalDetail(id));
    refetch();
  }

  const list = goals ?? [];

  return (
    <div>
      {review && review.cycle_name && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-timeline" /> Review timeline — {review.cycle_name}</div>
          </div>
          <div style={{ padding: "16px 24px", display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)" }}>SELF REVIEW</div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{review.self_submitted_at ? "Submitted" : "Not submitted"}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)" }}>MANAGER REVIEW</div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{review.manager_submitted_at ? "Submitted" : "Pending"}</div>
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)" }}>STATUS</div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{review.status_display}</div>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-target-arrow" /> Add a goal</div>
        </div>
        <div style={{ padding: "20px 24px" }}>
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
              <label className="field-label">Due Date</label>
              <input className="field-input" type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} />
            </div>
          </div>
          <button className="btn btn-filled" onClick={handleAdd} disabled={adding || !title.trim()}>
            {adding ? "Adding…" : "Add Goal"}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-list-details" /> My goals</div>
        </div>
        {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
        {loading ? (
          <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading…</h3></div>
        ) : list.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-target-arrow" />
            <h3>No goals yet</h3>
            <p>Add a goal above for the active review cycle.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Goal</th>
                  <th>Target</th>
                  <th>Due</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {list.map(g => (
                  <tr key={g.id}>
                    <td style={{ fontWeight: 600 }}>{g.title}</td>
                    <td style={{ color: "var(--on-variant)" }}>{g.target_metric || "—"}</td>
                    <td style={{ color: "var(--on-variant)" }}>{g.due_date || "—"}</td>
                    <td>
                      <select className="field-input field-select" style={{ padding: "4px 8px", fontSize: 12 }} value={g.status} onChange={e => updateStatus(g.id, e.target.value)}>
                        {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                      </select>
                      <span className={`badge ${STATUS_BADGE[g.status]}`} style={{ marginLeft: 6 }}>{STATUS_LABEL[g.status]}</span>
                    </td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => remove(g.id)}>
                        <i className="ti ti-trash" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
