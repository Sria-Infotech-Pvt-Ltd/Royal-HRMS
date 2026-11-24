"use client";

// The input for the new value of one profile field, drawn by the field's kind (date, choice list, number-like or plain text). Used by
// the employee's correction form and by HR when they type the value for an older request.

import { tr } from "@/lib/i18n/tr";
import DateInput from "@/components/shared/DateInput";
import type { ProfileChangeField } from "@/types/hrHelp";

interface ProfileChangeValueInputProps {
  spec: ProfileChangeField;
  value: string;
  onChange: (value: string) => void;
}

export default function ProfileChangeValueInput({ spec, value, onChange }: ProfileChangeValueInputProps) {
  if (spec.kind === "date") return <DateInput value={value} onChange={onChange} className="field-input" separator="-" />;
  if (spec.kind === "choice") {
    return (
      <select className="field-input field-select" value={value} onChange={event => onChange(event.target.value)} suppressHydrationWarning>
        <option value="">{tr("Select…")}</option>
        {spec.choices.map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select>
    );
  }
  if (spec.kind === "account") {
    // Digits only, as typed: a bank account number never contains spaces or letters.
    return (
      <input
        className="field-input" value={value} maxLength={spec.max_length} inputMode="numeric" autoComplete="off"
        onChange={event => onChange(event.target.value.replace(/\D/g, ""))} placeholder={tr("9 to 18 digits")}
      />
    );
  }
  if (spec.kind === "ifsc") {
    return (
      <input
        className="field-input" value={value} maxLength={spec.max_length} autoCapitalize="characters" autoComplete="off"
        onChange={event => onChange(event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""))} placeholder={tr("e.g. SBIN0001234")}
      />
    );
  }
  return (
    <input
      className="field-input" value={value} maxLength={spec.max_length} onChange={event => onChange(event.target.value)}
      inputMode={spec.kind === "phone" || spec.kind === "pin" ? "numeric" : undefined} placeholder={tr("New {field}", { field: spec.label.toLowerCase() })}
    />
  );
}
