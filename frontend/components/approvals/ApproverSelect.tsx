"use client";

import SearchableSelect from "@/components/SearchableSelect";
import FieldError from "@/components/shared/FieldError";
import type { ApproverOption, PersonRef } from "@/types/approvers";
import { optionLabel, personLine } from "./approverLabels";

interface Props {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: ApproverOption[];
  placeholder: string;
  hint?: string;
  error?: string;
  disabled?: boolean;
  /** The person already assigned, so they stay selectable (and labelled) even if they would no longer be offered. */
  assigned?: PersonRef | null;
}

/** One approver dropdown: each choice shows name, role, branch and department. */
export default function ApproverSelect({ label, value, onChange, options, placeholder, hint, error, disabled, assigned }: Props) {
  const choices = options.map(person => ({ value: person.id, label: optionLabel(person) }));
  if (value && assigned?.id === value && !options.some(person => person.id === value)) {
    choices.unshift({ value, label: `${personLine(assigned)} (no longer eligible)` });
  }
  return (
    <div className="f">
      <label>{label}</label>
      <SearchableSelect value={value} onChange={onChange} options={choices} placeholder={placeholder} disabled={disabled} />
      {hint && <small style={{ display: "block", marginTop: 4, color: "var(--on-variant)" }}>{hint}</small>}
      <FieldError message={error} />
    </div>
  );
}
