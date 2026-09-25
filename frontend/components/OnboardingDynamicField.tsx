"use client";

import type { OnboardingFieldConfig } from "@/types/onboardingFieldConfig";
import CountrySelect from "@/components/CountrySelect";

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

// current_pin_code/permanent_pin_code are plain 'text' fields (server-side
// validated in EmployeeProfileSerializer) but get the same digits-only,
// 6-character input mask the Company address form's PIN field already uses
// (AddressCard.tsx) — restricting keystrokes here catches typos immediately
// instead of only at save time.
const PIN_CODE_FIELDS = new Set(['current_pin_code', 'permanent_pin_code']);

// current_address/permanent_address are 'textarea' field_type (needed so
// DynamicStepFields.buildRuns gives each its own full-width row instead of
// packing it into the grid alongside father_name/blood_group/etc — see
// that file's own comment) but only ever hold one short house/street line
// (village/district/state/PIN are their own separate fields), so a real
// multi-row <textarea> is far taller than the content needs. Rendered as a
// single-line input instead, purely a display choice — field_type stays
// 'textarea' for the row-grouping logic above.
const ADDRESS_LINE_FIELDS = new Set(['current_address', 'permanent_address']);

// international_worker_country is seeded as a plain 'text' field (migration
// 0150) but is really "pick a country" — rendered from the shared master
// country list (lib/countries.ts) instead of a free-text box, the same way
// gender/marital_status/blood_group above are special-cased rather than
// changing the backend's field_type (avoids a config data migration for a
// purely-frontend rendering choice).
const COUNTRY_NAME_FIELDS = new Set(['international_worker_country']);

// nationality gets the same CountrySelect the Hire wizard's own Personal
// identity step already uses (HireWizardClient.tsx) — demonym mode
// ("Indian", "American") rather than country name, matching what this field
// actually stores. Previously rendered as a plain native <select> here,
// visually inconsistent with the polished searchable dropdown HR sees at
// hire time for the exact same field.
const NATIONALITY_FIELDS = new Set(['nationality']);

interface Props {
  config: OnboardingFieldConfig;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function DynamicField({ config, value, onChange, placeholder }: Props) {
  const choiceOptions = BUILTIN_CHOICE_FIELDS[config.field_key];
  const isPinCode = PIN_CODE_FIELDS.has(config.field_key);

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
        <select className={`${INP} field-select`} value={value} onChange={e => onChange(e.target.value)}>
          <option value="">Select</option>
          {choiceOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
    );
  }

  if (COUNTRY_NAME_FIELDS.has(config.field_key)) {
    return (
      <div className="field-group">
        {label}
        <CountrySelect value={value} onChange={onChange} mode="name" />
      </div>
    );
  }

  if (NATIONALITY_FIELDS.has(config.field_key)) {
    return (
      <div className="field-group">
        {label}
        <CountrySelect value={value} onChange={onChange} mode="demonym" />
      </div>
    );
  }

  if (config.field_type === "dropdown") {
    return (
      <div className="field-group">
        {label}
        <select className={`${INP} field-select`} value={value} onChange={e => onChange(e.target.value)}>
          <option value="">Select</option>
          {config.options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </div>
    );
  }

  if (config.field_type === "textarea") {
    if (ADDRESS_LINE_FIELDS.has(config.field_key)) {
      return (
        <div className="field-group">
          {label}
          <input className={INP} type="text" value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} />
        </div>
      );
    }
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
        onChange={e => onChange(isPinCode ? e.target.value.replace(/\D/g, "").slice(0, 6) : e.target.value)}
        placeholder={isPinCode ? "e.g. 500081" : placeholder}
        inputMode={isPinCode ? "numeric" : undefined}
        maxLength={isPinCode ? 6 : undefined}
      />
    </div>
  );
}
