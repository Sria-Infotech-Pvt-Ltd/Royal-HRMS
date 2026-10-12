"use client";

// One direct report's appraisal, from the Reporting Manager's side: read the
// employee's self-review (per-goal ratings, outcomes, evidence), then either
// send it back for changes (with a reason) or record the assessment, development
// plan and next check-in and send it to HR calibration. The API enforces that
// only the employee's reporting manager (or HR) can do this.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";
import { RATING_OPTIONS, managerStageLabel, type ReviewGoal, type TeamReview } from "@/types/appraisal";
import DateInput from "@/components/shared/DateInput";

interface Props {
  review: TeamReview;
  onClose: () => void;
  onChanged: () => void;
}

function message(error: unknown, fallback: string): string {
  return (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

export default function TeamReviewModal({ review, onClose, onChanged }: Props) {
  const { showToast } = useToast();
  const { data: goals } = useFetch<ReviewGoal[]>(review.self_submitted_at || review.manager_submitted_at ? API.performance.reviewGoals(review.id) : null);

  const myTurn = review.status === "self_review";
  const [rating, setRating] = useState(review.manager_rating);
  const [checkIn, setCheckIn] = useState(review.manager_next_checkin ?? "");
  const [comments, setComments] = useState(review.manager_notes);
  const [plan, setPlan] = useState(review.manager_development_plan);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function returnToEmployee() {
    // The assessment-comments box doubles as the reason, as in the reference.
    if (!comments.trim()) { setError("Enter what the employee should revise in the assessment comments."); return; }
    setBusy(true); setError("");
    try {
      await clientApi.post(API.performance.returnReview(review.id), { reason: comments.trim() });
      showToast("Returned to employee — the self-review is editable again.", "success");
      onChanged(); onClose();
    } catch (e) { setError(message(e, "Could not return this review.")); } finally { setBusy(false); }
  }

  async function sendToHr() {
    if (!rating || !comments.trim() || !plan.trim() || !checkIn) {
      setError("Add a rating, assessment comments, a development plan and the next check-in date."); return;
    }
    setBusy(true); setError("");
    try {
      await clientApi.patch(API.performance.reviewDetail(review.id), {
        manager_rating: rating, manager_notes: comments.trim(),
        manager_development_plan: plan.trim(), manager_next_checkin: checkIn,
      });
      await clientApi.post(API.performance.submitManagerReview(review.id));
      showToast("Sent to HR — the manager assessment is now awaiting calibration.", "success");
      onChanged(); onClose();
    } catch (e) { setError(message(e, "Could not send this review to HR.")); } finally { setBusy(false); }
  }

  return (
    <Modal
      title={<h2 className="modal-title">Appraisal <em style={{ color: "var(--brand-ink)" }}>review</em></h2>}
      onClose={onClose} size="lg" closeDisabled={busy} scrollBody
      footer={
        <>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={busy}>Close</button>
          {myTurn && (
            <>
              <button className="btn btn-outline" type="button" onClick={returnToEmployee} disabled={busy}>Return to employee</button>
              <button className="btn btn-filled" type="button" onClick={sendToHr} disabled={busy}>{busy ? "Working…" : "Send to HR calibration"}</button>
            </>
          )}
        </>
      }
    >
      <div className="space-y-4">
        <div className="ess-pagehead">
          <div>
            <h2>{review.employee_name}</h2>
            <p>{review.cycle_name} · {review.employee_code}</p>
          </div>
          <span className="appraisal-status">{managerStageLabel(review.status)}</span>
        </div>

        {review.status === "returned" && (
          <div className="pay-callout"><b>Returned for changes</b><p>{review.return_reason}</p></div>
        )}
        {error && <div className="alert alert-error">{error}</div>}

        {!review.self_submitted_at && !review.manager_submitted_at ? (
          <p className="hint">Waiting for the employee to submit their self-review. Self-review due {review.cycle_self_review_due ? formatDate(review.cycle_self_review_due) : "—"}.</p>
        ) : (
          <div className="ess-card">
            <h2>Submitted self-review</h2>
            <p>{review.self_submitted_at ? `Sent ${formatDate(review.self_submitted_at)}.` : "Submitted."} Their original responses stay available for reference.</p>
            {(goals ?? []).map(g => (
              <div key={g.id} className="appraisal-goal">
                <h3>{g.title}{g.weight_percent ? ` · ${g.weight_percent}% weight` : ""} · Self rating {g.self_rating || "—"}/5</h3>
                <p>{g.target_metric || g.description}</p>
                <div className="request-summary">
                  <div className="request-fact"><small>OUTCOME</small><b>{g.outcome_measure || "—"}</b></div>
                  <div className="request-fact"><small>EVIDENCE</small><b>{g.evidence_reference || "—"}</b></div>
                </div>
                {g.self_comments && <p className="appraisal-read" style={{ marginTop: 10 }}>{g.self_comments}</p>}
              </div>
            ))}
            <div className="request-summary" style={{ marginTop: 12 }}>
              <div className="request-fact"><small>STRENGTHS</small><b>{review.key_strengths || "—"}</b></div>
              <div className="request-fact"><small>DEVELOPMENT</small><b>{review.development_areas || "—"}</b></div>
              <div className="request-fact"><small>SUPPORT</small><b>{review.support_needed || "—"}</b></div>
              <div className="request-fact"><small>NEXT GOAL</small><b>{review.next_cycle_goal || "—"}</b></div>
            </div>
          </div>
        )}

        {myTurn ? (
          <div className="ess-card">
            <h2>Manager assessment</h2>
            <p>Assess the submitted evidence and propose a development plan.</p>
            <div className="ess-form">
              <div className="ess-field">
                <label htmlFor="tmRating">MANAGER RATING</label>
                <select id="tmRating" value={rating} onChange={e => setRating(e.target.value)}>
                  <option value="">Choose rating</option>
                  {RATING_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
              <div className="ess-field">
                <label htmlFor="tmCheckIn">NEXT CHECK-IN</label>
                <DateInput id="tmCheckIn" value={checkIn} onChange={isoDate => setCheckIn(isoDate)} />
              </div>
              <div className="ess-field">
                <label htmlFor="tmComments">ASSESSMENT COMMENTS</label>
                <textarea id="tmComments" value={comments} onChange={e => setComments(e.target.value)} placeholder="Evidence-based evaluation" />
              </div>
              <div className="ess-field">
                <label htmlFor="tmPlan">DEVELOPMENT PLAN</label>
                <textarea id="tmPlan" value={plan} onChange={e => setPlan(e.target.value)} placeholder="Action, owner, target date and measure" />
              </div>
            </div>
          </div>
        ) : review.manager_submitted_at ? (
          <div className="ess-card">
            <h2>Your assessment</h2>
            <p>Sent to HR on {formatDate(review.manager_submitted_at)}.</p>
            <div className="request-summary">
              <div className="request-fact"><small>RATING</small><b>{review.manager_rating || "—"} / 5</b></div>
              <div className="request-fact"><small>NEXT CHECK-IN</small><b>{review.manager_next_checkin ? formatDate(review.manager_next_checkin) : "—"}</b></div>
              <div className="request-fact"><small>COMMENTS</small><b>{review.manager_notes || "—"}</b></div>
              <div className="request-fact"><small>DEVELOPMENT PLAN</small><b>{review.manager_development_plan || "—"}</b></div>
            </div>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
