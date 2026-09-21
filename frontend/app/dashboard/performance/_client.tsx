"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import CreateCycleModal from "./_components/CreateCycleModal";
import ReviewActionModal from "./_components/ReviewActionModal";
import ReviewQueueRowActions from "./_components/ReviewQueueRowActions";

export interface ApiCycle {
  id: string;
  name: string;
  period_start: string;
  period_end: string;
  self_review_due: string;
  manager_review_due: string;
  status: "draft" | "active" | "closed";
}

export interface ApiReview {
  id: string;
  employee_name: string;
  employee_code: string;
  cycle_name: string;
  metric_reference: string;
  what_changed: string;
  key_strengths: string;
  development_areas: string;
  support_needed: string;
  next_cycle_goal: string;
  self_rating: string;
  self_submitted_at: string | null;
  manager_name: string;
  manager_rating: string;
  manager_notes: string;
  manager_submitted_at: string | null;
  hr_calibrated_at: string | null;
  published_at: string | null;
  acknowledged_at: string | null;
  status: "not_started" | "self_review" | "hr_calibration" | "published" | "completed";
  status_display: string;
}

interface HrQueueData {
  cycle: ApiCycle | null;
  reviews: ApiReview[];
  stats: {
    total_employees_with_reviews: number;
    self_reviews_done: number;
    manager_reviews_done: number;
    goals_at_risk: number;
  } | null;
}

const STATUS_BADGE: Record<string, string> = {
  not_started: "badge-neutral", self_review: "badge-warn", hr_calibration: "badge-warn",
  published: "badge-info", completed: "badge-success",
};
const CYCLE_BADGE: Record<string, string> = {
  draft: "badge-neutral", active: "badge-success", closed: "badge-neutral",
};

const pct = (done: number, total: number) => (total === 0 ? "—" : `${Math.round((done / total) * 100)}%`);

export default function PerformanceClient({ onBack }: { onBack?: () => void }) {
  const { data: queue, loading, error, refetch } = useFetch<HrQueueData>(API.performance.hrQueue);
  const { data: cycles, refetch: refetchCycles } = useFetch<ApiCycle[]>(API.performance.cycles);

  const [showCreate, setShowCreate] = useState(false);
  const [reviewing, setReviewing] = useState<ApiReview | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const stats = queue?.stats;
  const total = stats?.total_employees_with_reviews ?? 0;

  async function activateCycle(id: string) {
    setBusyId(id);
    try {
      await clientApi.patch(API.performance.cycleDetail(id), { status: "active" });
      refetchCycles();
      refetch();
    } finally {
      setBusyId(null);
    }
  }

  async function closeCycle(id: string) {
    setBusyId(id);
    try {
      await clientApi.patch(API.performance.cycleDetail(id), { status: "closed" });
      refetchCycles();
      refetch();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          {onBack && (
            <button
              onClick={onBack}
              style={{ display: "flex", alignItems: "center", gap: 4, background: "none", border: "none", color: "var(--primary)", fontSize: 12.5, fontWeight: 700, cursor: "pointer", padding: 0, marginBottom: 8 }}
            >
              <i className="ti ti-arrow-left" /> Back to overview
            </button>
          )}
          <div className="page-title">Performance Reviews</div>
          <div className="page-sub">Track goals, self-reviews and manager reviews for the active cycle.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowCreate(true)}>
            <i className="ti ti-plus" /> New review cycle
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-16">{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 1, background: "var(--outline-v)", borderRadius: "var(--radius-lg)", overflow: "hidden", marginBottom: 20 }}>
        <div style={{ background: "var(--surface)", padding: "18px 22px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>ACTIVE CYCLE</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", marginTop: 4 }}>{queue?.cycle?.name ?? "None"}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{queue?.cycle ? `Closes ${queue.cycle.period_end}` : "Create and activate a cycle"}</div>
        </div>
        <div style={{ background: "var(--surface)", padding: "18px 22px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>SELF REVIEWS</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", marginTop: 4 }}>{stats ? pct(stats.self_reviews_done, total) : "—"}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{stats ? `${stats.self_reviews_done} of ${total} complete` : ""}</div>
        </div>
        <div style={{ background: "var(--surface)", padding: "18px 22px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>MANAGER REVIEWS</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", marginTop: 4 }}>{stats ? pct(stats.manager_reviews_done, total) : "—"}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{stats ? `${stats.manager_reviews_done} of ${total} complete` : ""}</div>
        </div>
        <div style={{ background: "var(--surface)", padding: "18px 22px" }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>GOALS AT RISK</div>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--on-bg)", marginTop: 4 }}>{stats?.goals_at_risk ?? "—"}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Needs follow-up</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calendar-time" /> Review cycles</div>
        </div>
        {!cycles || cycles.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-calendar-time" />
            <h3>No review cycles yet</h3>
            <p>Create one to start collecting goals and reviews.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Period</th>
                  <th>Self-Review Due</th>
                  <th>Manager Review Due</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {cycles.map(c => (
                  <tr key={c.id}>
                    <td style={{ fontWeight: 600 }}>{c.name}</td>
                    <td style={{ color: "var(--on-variant)" }}>{c.period_start} – {c.period_end}</td>
                    <td style={{ color: "var(--on-variant)" }}>{c.self_review_due}</td>
                    <td style={{ color: "var(--on-variant)" }}>{c.manager_review_due}</td>
                    <td><span className={`badge ${CYCLE_BADGE[c.status]}`}>{c.status}</span></td>
                    <td>
                      {c.status === "draft" && (
                        <button className="btn btn-filled btn-sm" onClick={() => activateCycle(c.id)} disabled={busyId === c.id}>
                          Activate
                        </button>
                      )}
                      {c.status === "active" && (
                        <button className="btn btn-ghost btn-sm" onClick={() => closeCycle(c.id)} disabled={busyId === c.id}>
                          Close
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-list-details" /> HR review queue</div>
        </div>
        {loading ? (
          <div className="empty-state">
            <i className="ti ti-loader-2 spin" />
            <h3>Loading…</h3>
          </div>
        ) : !queue?.cycle ? (
          <div className="empty-state">
            <i className="ti ti-list-details" />
            <h3>No active review cycle</h3>
            <p>Activate a cycle above to start the review queue.</p>
          </div>
        ) : queue.reviews.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-list-details" />
            <h3>No employee reviews yet</h3>
            <p>Reviews appear here once an employee opens their Appraisals tab.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Employee</th>
                  <th>Self Review</th>
                  <th>Manager</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {queue.reviews.map(r => (
                  <tr key={r.id}>
                    <td style={{ fontWeight: 600 }}>{r.employee_name} <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>· {r.employee_code}</span></td>
                    <td>{r.self_submitted_at ? "Submitted" : "Not submitted"}</td>
                    <td>{r.manager_name || "—"}</td>
                    <td><span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status_display}</span></td>
                    <td>
                      <ReviewQueueRowActions review={r} onReview={setReviewing} onChanged={refetch} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showCreate && (
        <CreateCycleModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); refetchCycles(); }}
        />
      )}

      {reviewing && (
        <ReviewActionModal
          review={reviewing}
          onClose={() => setReviewing(null)}
          onSaved={() => { setReviewing(null); refetch(); }}
        />
      )}
    </div>
  );
}
