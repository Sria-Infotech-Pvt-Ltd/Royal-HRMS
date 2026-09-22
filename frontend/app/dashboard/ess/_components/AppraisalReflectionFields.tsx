"use client";

// The four cycle-wide reflection textareas below the per-goal self-review
// cards on "My appraisal" — split out of AppraisalsTab.tsx purely to keep
// that file under the project's ~300-line guideline.

export interface AppraisalReflectionForm {
  key_strengths: string;
  development_areas: string;
  support_needed: string;
  next_cycle_goal: string;
}

interface Props {
  value: AppraisalReflectionForm;
  disabled: boolean;
  onChange: (field: keyof AppraisalReflectionForm, value: string) => void;
}

const FIELDS: { key: keyof AppraisalReflectionForm; label: string; placeholder: string }[] = [
  { key: "key_strengths",     label: "Key strengths",                 placeholder: "Impact you are proud of" },
  { key: "development_areas", label: "Development areas",             placeholder: "What would you improve?" },
  { key: "support_needed",    label: "Support needed",                placeholder: "Coaching, tools or training needed" },
  { key: "next_cycle_goal",   label: "Next-cycle development goal",   placeholder: "One measurable development goal" },
];

export default function AppraisalReflectionFields({ value, disabled, onChange }: Props) {
  return (
    <div className="form-row cols-2 mb-16">
      {FIELDS.map(field => (
        <div key={field.key} className="field-group">
          <label className="field-label">{field.label}</label>
          <textarea
            className="field-input"
            rows={2}
            disabled={disabled}
            placeholder={field.placeholder}
            value={value[field.key]}
            onChange={e => onChange(field.key, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
}
