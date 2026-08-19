"use client";

import type { OnboardingFieldConfig } from "@/types/onboardingFieldConfig";

const INP = "field-input";

const Req = () => <span style={{ color: "var(--error, #dc2626)", marginLeft: 2 }}>*</span>;

// Four built-in fields are backed by a fixed backend choice set
// (EmployeeProfile.GENDER_CHOICES etc) where the stored value ('male') and
// the displayed label ('Male') differ — OnboardingFieldConfig.options is a
// plain string list with no value/label split, so these four are rendered
// from their own hardcoded pairs instead of the generic dropdown path.
// Every other field, including any future built-in addition and all
// HR-created custom fields, renders generically from field_type/options.
const BUILTIN_CHOICE_FIELDS: Record<string, { value: string; label: string }[]> = {
  gender: [
    { value: "male", label: "Male" },
    { value: "female", label: "Female" },
    { value: "other", label: "Other / Prefer not to say" },
  ],
  marital_status: [
    { value: "single", label: "Single" },
    { value: "married", label: "Married" },
    { value: "divorced", label: "Divorced" },
    { value: "widowed", label: "Widowed" },
  ],
  blood_group: ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"].map(g => ({ value: g, label: g })),
  account_type: [
    { value: "savings", label: "Savings" },
    { value: "current", label: "Current" },
  ],
};

interface Props {
  config: OnboardingFieldConfig;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function DynamicField({ config, value, onChange, placeholder }: Props) {
  const choiceOptions = BUILTIN_CHOICE_FIELDS[config.field_key];

  const label = (
    <label className="field-label">
      {config.label}
      {config.required && <Req />}
    </label>
  );

  if (choiceOptions) {
    return (
      <div className="field-group">
        {label}
        <select className={INP} value={value} onChange={e => onChange(e.target.value)}>
          <option value="">Select</option>
          {choiceOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
    );
  }

  if (config.field_type === "dropdown") {
    return (
      <div className="field-group">
        {label}
        <select className={INP} value={value} onChange={e => onChange(e.target.value)}>
          <option value="">Select</option>
          {config.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    );
  }

  if (config.field_type === "textarea") {
    return (
      <div className="field-group">
        {label}
        <textarea className={INP} rows={2} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
      </div>
    );
  }

  if (config.field_type === "checkbox") {
    return (
      <label className="module-check">
        <input type="checkbox" checked={value === "true"} onChange={e => onChange(e.target.checked ? "true" : "false")} />
        <span>{config.label}{config.required && <Req />}</span>
      </label>
    );
  }

  return (
    <div className="field-group">
      {label}
      <input
        type={config.field_type === "date" ? "date" : config.field_type === "number" ? "number" : "text"}
        className={INP}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
