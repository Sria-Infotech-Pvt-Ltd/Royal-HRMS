"use client";

// One per-goal self-review sub-card inside the "Self-review" card — goal
// title + weight, then a 2x2 field grid (self rating / outcome measure /
// evidence reference / comments). Split out of AppraisalsTab.tsx to keep
// that file's length down, same composition pattern HomeTab.tsx's siblings
// (HomeBanner.tsx etc.) use.

export interface AppraisalGoalFormValue {
  self_rating: string;
  outcome_measure: string;
  evidence_reference: string;
  self_comments: string;
}

export interface AppraisalGoalCardData {
  id: string;
  title: string;
  description: string;
  weight_percent: number | null;
}

interface Props {
  goal: AppraisalGoalCardData;
  value: AppraisalGoalFormValue;
  disabled: boolean;
  onChange: (goalId: string, field: keyof AppraisalGoalFormValue, value: string) => void;
}

export default function AppraisalGoalCard({ goal, value, disabled, onChange }: Props) {
  return (
    <div className="card mb-16" style={{ background: "var(--bg-low)" }}>
      <div style={{ padding: "16px 20px 4px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
          <h4 style={{ fontSize: "0.95rem", margin: 0 }}>{goal.title}</h4>
          {goal.weight_percent !== null && (
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
              {goal.weight_percent}% weight
            </span>
          )}
        </div>
        {goal.description && (
          <p style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>{goal.description}</p>
        )}
      </div>

      <div style={{ padding: "8px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="field-group">
          <label className="field-label">Self rating</label>
          <select
            className="field-input field-select"
            disabled={disabled}
            value={value.self_rating}
            onChange={e => onChange(goal.id, "self_rating", e.target.value)}
          >
            <option value="">Choose rating</option>
            {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Outcome / measure</label>
          <input
            className="field-input"
            disabled={disabled}
            placeholder="e.g. 22% fewer incidents"
            value={value.outcome_measure}
            onChange={e => onChange(goal.id, "outcome_measure", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Evidence or link reference</label>
          <textarea
            className="field-input"
            rows={2}
            disabled={disabled}
            placeholder="Metric, project or document reference"
            value={value.evidence_reference}
            onChange={e => onChange(goal.id, "evidence_reference", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">My comments</label>
          <textarea
            className="field-input"
            rows={2}
            disabled={disabled}
            placeholder="What changed and why?"
            value={value.self_comments}
            onChange={e => onChange(goal.id, "self_comments", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}
