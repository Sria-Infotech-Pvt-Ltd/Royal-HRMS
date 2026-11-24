"use client";

// "Published appraisal outcome" — shown to the employee only once HR has
// published the review (the API withholds the manager assessment and the
// calibrated rating until then). Reading + acknowledging: the checkbox makes
// explicit that acknowledging means "I have read this", not "I agree".

import { useState } from "react";
import { formatDate } from "@/lib/formatDate";
import { useT } from "@/hooks/useI18n";

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
  const t = useT();
  const [comment, setComment] = useState("");
  const [read, setRead] = useState(false);

  return (
    <div className="ess-card">
      <h2>{t("Published appraisal outcome")}</h2>
      <p>{t("Manager assessment and final rating are visible only after HR publication.")}</p>

      <div className="request-summary">
        <div className="request-fact"><small>{t("MANAGER RATING")}</small><b>{t("{rating} / 5", { rating: outcome.manager_rating || "—" })}</b></div>
        <div className="request-fact"><small>{t("FINAL RATING")}</small><b>{t("{rating} / 5", { rating: outcome.final_rating || "—" })}</b></div>
        <div className="request-fact"><small>{t("MANAGER COMMENTS")}</small><b>{outcome.manager_notes || "—"}</b></div>
        <div className="request-fact"><small>{t("CALIBRATION NOTE")}</small><b>{outcome.calibration_note || "—"}</b></div>
      </div>
      <div className="request-fact" style={{ marginTop: 10 }}>
        <small>{t("DEVELOPMENT PLAN")}</small><b>{outcome.manager_development_plan || "—"}</b>
      </div>
      <div className="request-fact" style={{ marginTop: 10 }}>
        <small>{t("NEXT CHECK-IN")}</small><b>{outcome.manager_next_checkin ? formatDate(outcome.manager_next_checkin) : "—"}</b>
      </div>

      {outcome.acknowledged_at ? (
        <div className="pay-callout" style={{ marginTop: 12 }}>
          <b>{t("Acknowledged {date}", { date: formatDate(outcome.acknowledged_at) })}</b>
          <p>{outcome.acknowledgement_comment || t("No additional response")}</p>
        </div>
      ) : (
        <>
          <div className="ess-form" style={{ marginTop: 14 }}>
            <div className="ess-field">
              <label htmlFor="appEmployeeComment">{t("MY RESPONSE (OPTIONAL)")}</label>
              <textarea
                id="appEmployeeComment" value={comment} onChange={e => setComment(e.target.value)}
                placeholder={t("Add a response or question for the review conversation")}
              />
            </div>
            <div className="ess-field">
              <label>
                <input type="checkbox" checked={read} onChange={e => setRead(e.target.checked)} style={{ width: "auto", marginRight: 8 }} />
                {t("I have read this appraisal. Acknowledgement does not mean I agree with every rating.")}
              </label>
            </div>
          </div>
          <div className="appraisal-actions">
            <button className="btn btn-filled" type="button" disabled={!read || acknowledging} onClick={() => onAcknowledge(comment.trim())}>
              {acknowledging ? t("Acknowledging…") : t("Acknowledge appraisal")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
