"use client";

// "Published appraisal outcome" — shown to the employee only once HR has
// published the review (the API withholds the manager assessment and the
// calibrated rating until then). Reading + acknowledging: the checkbox makes
// explicit that acknowledging means "I have read this", not "I agree".

import { useState } from "react";
import { formatDate } from "@/lib/formatDate";

export interface AppraisalOutcome {
  manager_rating: string;
  manager_notes: string;
  manager_development_plan: string;
  manager_next_checkin: string | null;
  final_rating: string;
  calibration_note: string;
  acknowledged_at: string | null;
  acknowledgement_comment: string;
}

interface Props {
  outcome: AppraisalOutcome;
  acknowledging: boolean;
  onAcknowledge: (comment: string) => void;
}

export default function AppraisalOutcomeCard({ outcome, acknowledging, onAcknowledge }: Props) {
  const [comment, setComment] = useState("");
  const [read, setRead] = useState(false);

  return (
    <div className="ess-card">
      <h2>Published appraisal outcome</h2>
      <p>Manager assessment and final rating are visible only after HR publication.</p>

      <div className="request-summary">
        <div className="request-fact"><small>MANAGER RATING</small><b>{outcome.manager_rating || "—"} / 5</b></div>
        <div className="request-fact"><small>FINAL RATING</small><b>{outcome.final_rating || "—"} / 5</b></div>
        <div className="request-fact"><small>MANAGER COMMENTS</small><b>{outcome.manager_notes || "—"}</b></div>
        <div className="request-fact"><small>CALIBRATION NOTE</small><b>{outcome.calibration_note || "—"}</b></div>
      </div>
      <div className="request-fact" style={{ marginTop: 10 }}>
        <small>DEVELOPMENT PLAN</small><b>{outcome.manager_development_plan || "—"}</b>
      </div>
      <div className="request-fact" style={{ marginTop: 10 }}>
        <small>NEXT CHECK-IN</small><b>{outcome.manager_next_checkin ? formatDate(outcome.manager_next_checkin) : "—"}</b>
      </div>

      {outcome.acknowledged_at ? (
        <div className="pay-callout" style={{ marginTop: 12 }}>
          <b>Acknowledged {formatDate(outcome.acknowledged_at)}</b>
          <p>{outcome.acknowledgement_comment || "No additional response"}</p>
        </div>
      ) : (
        <>
          <div className="ess-form" style={{ marginTop: 14 }}>
            <div className="ess-field">
              <label htmlFor="appEmployeeComment">MY RESPONSE (OPTIONAL)</label>
              <textarea
                id="appEmployeeComment" value={comment} onChange={e => setComment(e.target.value)}
                placeholder="Add a response or question for the review conversation"
              />
            </div>
            <div className="ess-field">
              <label>
                <input type="checkbox" checked={read} onChange={e => setRead(e.target.checked)} style={{ width: "auto", marginRight: 8 }} />
                I have read this appraisal. Acknowledgement does not mean I agree with every rating.
              </label>
            </div>
          </div>
          <div className="appraisal-actions">
            <button className="btn btn-filled" type="button" disabled={!read || acknowledging} onClick={() => onAcknowledge(comment.trim())}>
              {acknowledging ? "Acknowledging…" : "Acknowledge appraisal"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
