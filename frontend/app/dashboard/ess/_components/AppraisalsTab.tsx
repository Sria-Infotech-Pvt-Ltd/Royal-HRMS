"use client";

// Appraisals — "My appraisal": one self-review sub-card per goal (rating,
// outcome, evidence, comments) plus the cycle-wide reflection fields (key
// strengths, development areas, support needed, next-cycle goal), a
// 4-step review-stage tracker, and a derived activity history. Manager/HR
// fields stay read-only here — this tab is the employee's own self-review
// surface only.

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import AppraisalGoalCard, { AppraisalGoalFormValue } from "./AppraisalGoalCard";
import AppraisalStageTracker from "./AppraisalStageTracker";
import AppraisalActivityHistory, { AppraisalActivityEntry } from "./AppraisalActivityHistory";
import AppraisalReflectionFields, { AppraisalReflectionForm } from "./AppraisalReflectionFields";

interface ApiGoal {
  id: string;
  title: string;
  description: string;
  weight_percent: number | null;
  self_rating: string;
  outcome_measure: string;
  evidence_reference: string;
  self_comments: string;
}

interface ApiReview {
  id: string;
  cycle_name: string;
  cycle_self_review_due: string | null;
  cycle_manager_review_due: string | null;
  employee_name: string;
  employee_code: string;
  key_strengths: string;
  development_areas: string;
  support_needed: string;
  next_cycle_goal: string;
  self_submitted_at: string | null;
  manager_submitted_at: string | null;
  hr_calibrated_at: string | null;
  published_at: string | null;
  acknowledged_at: string | null;
  status: string;
  status_display: string;
  activity_history: AppraisalActivityEntry[];
}

type ReflectionForm = AppraisalReflectionForm;

const EMPTY_REFLECTION: ReflectionForm = {
  key_strengths: "", development_areas: "", support_needed: "", next_cycle_goal: "",
};

const EMPTY_GOAL_VALUE: AppraisalGoalFormValue = {
  self_rating: "", outcome_measure: "", evidence_reference: "", self_comments: "",
};

const STATUS_LINK_LABEL: Record<string, string> = {
  not_started:    "Self-review draft",
  self_review:    "Awaiting manager review",
  hr_calibration: "Awaiting HR calibration",
  published:      "Published",
  completed:      "Acknowledged",
};

function reviewCode(cycleName: string, employeeCode: string): string {
  const shortCycle = cycleName.split(" ")[0] || cycleName;
  return `APR-${shortCycle}-${employeeCode}`;
}

export default function AppraisalsTab() {
  const { data: review, loading: reviewLoading, error: reviewErr, refetch: refetchReview } =
    useFetch<ApiReview | null>(API.performance.myReview);
  const { data: goals, loading: goalsLoading, refetch: refetchGoals } =
    useFetch<ApiGoal[]>(API.performance.myGoals);

  const [reflection, setReflection] = useState<ReflectionForm>(EMPTY_REFLECTION);
  const [goalForms, setGoalForms] = useState<Record<string, AppraisalGoalFormValue>>({});
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [acknowledging, setAcknowledging] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!review) return;
    setReflection({
      key_strengths: review.key_strengths, development_areas: review.development_areas,
      support_needed: review.support_needed, next_cycle_goal: review.next_cycle_goal,
    });
  }, [review]);

  useEffect(() => {
    if (!goals) return;
    setGoalForms(prev => {
      const next: Record<string, AppraisalGoalFormValue> = {};
      for (const goal of goals) {
        next[goal.id] = prev[goal.id] ?? {
          self_rating: goal.self_rating, outcome_measure: goal.outcome_measure,
          evidence_reference: goal.evidence_reference, self_comments: goal.self_comments,
        };
      }
      return next;
    });
  }, [goals]);

  const isSubmitted = !!review?.self_submitted_at;

  function setReflectionField(field: keyof ReflectionForm, value: string) {
    setReflection(prev => ({ ...prev, [field]: value }));
  }

  function setGoalField(goalId: string, field: keyof AppraisalGoalFormValue, value: string) {
    setGoalForms(prev => ({ ...prev, [goalId]: { ...(prev[goalId] ?? EMPTY_GOAL_VALUE), [field]: value } }));
  }

  async function handleSave(): Promise<void> {
    setErr(null); setMsg(null); setSaving(true);
    try {
      await Promise.all([
        clientApi.patch(API.performance.myReview, reflection),
        ...Object.entries(goalForms).map(([goalId, value]) =>
          clientApi.patch(API.performance.myGoalDetail(goalId), value)),
      ]);
      setMsg("Draft saved.");
      refetchReview();
      refetchGoals();
    } catch (e: unknown) {
      const m = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(m ?? "Failed to save. Is there an active review cycle?");
      throw e;
    } finally {
      setSaving(false);
    }
  }

  async function handleSubmit(): Promise<void> {
    setErr(null); setMsg(null); setSubmitting(true);
    try {
      await handleSave();
      await clientApi.post(API.performance.submitMyReview);
      setMsg("Self-review submitted.");
      refetchReview();
    } catch (e: unknown) {
      const m = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(m ?? "Failed to submit.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleAcknowledge(): Promise<void> {
    if (!review) return;
    setErr(null); setMsg(null); setAcknowledging(true);
    try {
      await clientApi.post(API.performance.acknowledgeReview(review.id));
      setMsg("Outcome acknowledged.");
      refetchReview();
    } catch (e: unknown) {
      const m = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(m ?? "Failed to acknowledge outcome.");
    } finally {
      setAcknowledging(false);
    }
  }

  if (reviewLoading || goalsLoading) {
    return <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading…</h3></div>;
  }

  if (reviewErr) {
    return <div className="alert alert-error">{reviewErr}</div>;
  }

  if (!review || !review.id) {
    return (
      <div className="empty-state">
        <i className="ti ti-file-text" />
        <h3>No active review cycle</h3>
        <p>Your appraisal form will appear here once HR opens a review cycle.</p>
      </div>
    );
  }

  const goalList = goals ?? [];
  const statusLinkLabel = STATUS_LINK_LABEL[review.status] ?? review.status_display;
  const needsAcknowledge = !!review.published_at && !review.acknowledged_at;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: "1.3rem" }}>My appraisal</h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>
            {review.cycle_name} · {review.employee_name} · {reviewCode(review.cycle_name, review.employee_code)}
          </p>
        </div>
        <span style={{ color: "var(--primary)", fontWeight: 600, fontSize: 13, whiteSpace: "nowrap" }}>{statusLinkLabel}</span>
      </div>

      {err && <div className="alert alert-error mb-16">{err}</div>}
      {msg && <div className="alert alert-success mb-16">{msg}</div>}
      {isSubmitted && (
        <div className="alert alert-info mb-16">
          Your self-review has been submitted and can no longer be edited.
        </div>
      )}
      {needsAcknowledge && (
        <div className="alert alert-info mb-16" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12 }}>
          <span>Your appraisal outcome has been published. Please review and acknowledge it.</span>
          <button className="btn btn-filled btn-sm" onClick={handleAcknowledge} disabled={acknowledging}>
            {acknowledging ? "Acknowledging…" : "Acknowledge outcome"}
          </button>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, alignItems: "start" }}>
        <div style={{ minWidth: 0 }}>
          <div className="card mb-16">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-file-text" /> Self-review</div>
            </div>
            <div style={{ padding: "16px 20px 4px" }}>
              <p style={{ fontSize: 12, color: "var(--on-variant)", margin: 0 }}>
                Record outcomes against each goal, with evidence that your manager can verify.
              </p>
            </div>
            <div style={{ padding: "12px 20px 20px" }}>
              {goalList.length === 0 ? (
                <p style={{ fontSize: 13, color: "var(--on-variant)" }}>No goals set for this cycle yet.</p>
              ) : (
                goalList.map(goal => (
                  <AppraisalGoalCard
                    key={goal.id}
                    goal={goal}
                    value={goalForms[goal.id] ?? EMPTY_GOAL_VALUE}
                    disabled={isSubmitted}
                    onChange={setGoalField}
                  />
                ))
              )}

              <AppraisalReflectionFields value={reflection} disabled={isSubmitted} onChange={setReflectionField} />

              {!isSubmitted && (
                <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                  <button className="btn btn-ghost" onClick={handleSave} disabled={saving || submitting}>
                    {saving ? "Saving…" : "Save draft"}
                  </button>
                  <button className="btn btn-filled" onClick={handleSubmit} disabled={saving || submitting}>
                    {submitting ? "Submitting…" : "Submit self-review"}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        <div style={{ minWidth: 0 }}>
          <AppraisalStageTracker
            input={{
              selfSubmittedAt: review.self_submitted_at,
              managerSubmittedAt: review.manager_submitted_at,
              hrCalibratedAt: review.hr_calibrated_at,
              publishedAt: review.published_at,
              acknowledgedAt: review.acknowledged_at,
              selfReviewDue: review.cycle_self_review_due,
              managerReviewDue: review.cycle_manager_review_due,
            }}
          />
          <AppraisalActivityHistory entries={review.activity_history ?? []} />
        </div>
      </div>
    </div>
  );
}
