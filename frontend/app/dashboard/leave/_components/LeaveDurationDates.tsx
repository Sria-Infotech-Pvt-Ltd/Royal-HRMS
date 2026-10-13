"use client";

// Duration (segmented control) and start / end date fields of the leave request form.

import DateInput from "@/components/shared/DateInput";
import { fmtDate, type DurationKey } from "../_data";
import { Err, Lbl, dayName, type LeaveForm } from "./applyLeaveFormHelpers";

const DURATION_OPTIONS: { value: DurationKey; label: string }[] = [
  { value: "full_day",       label: "Full day" },
  { value: "half_morning",   label: "Morning half" },
  { value: "half_afternoon", label: "Afternoon half" },
];

interface Props {
  form: LeaveForm;
  errors: Record<string, string>;
  isHalfDay: boolean;
  onDurationChange: (value: DurationKey) => void;
  onDateChange: (field: "from_date" | "to_date", isoDate: string) => void;
}

export default function LeaveDurationDates({ form, errors, isHalfDay, onDurationChange, onDateChange }: Props) {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Lbl text="Duration" />
        <div role="radiogroup" aria-label="Duration" className="segmented">
          {DURATION_OPTIONS.map(option => {
            const isSelected = form.duration === option.value;
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => onDurationChange(option.value)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Lbl text={isHalfDay ? "Date" : "Start date"} required />
          <DateInput value={form.from_date} onChange={isoDate => onDateChange("from_date", isoDate)} className={`field-input${errors.from_date ? " field-error" : ""}`} />
          {form.from_date && !errors.from_date && (
            <p className="mt-1.5 text-xs text-[var(--on-variant)]">{dayName(form.from_date)}, {fmtDate(form.from_date)}</p>
          )}
          <Err msg={errors.from_date} />
        </div>
        {!isHalfDay && (
          <div>
            <Lbl text="End date" required />
            <DateInput value={form.to_date} min={form.from_date} onChange={isoDate => onDateChange("to_date", isoDate)} className={`field-input${errors.to_date ? " field-error" : ""}`} />
            {form.to_date && !errors.to_date && (
              <p className="mt-1.5 text-xs text-[var(--on-variant)]">{dayName(form.to_date)}, {fmtDate(form.to_date)}</p>
            )}
            <Err msg={errors.to_date} />
          </div>
        )}
      </div>
    </div>
  );
}
