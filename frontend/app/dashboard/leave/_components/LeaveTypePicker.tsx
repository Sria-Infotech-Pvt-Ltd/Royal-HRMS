"use client";

// Leave type choice: a plain grid of selectable options showing the balance as text.
// The detailed balance bar lives in the summary panel, so these stay light.

import { LEAVE_TYPES_LIST, fmtDate, type LeaveBalance, type LeaveTypeKey } from "../_data";

interface Props {
  selected: LeaveTypeKey;
  balanceMap: Record<string, LeaveBalance | undefined>;
  onSelect: (key: LeaveTypeKey) => void;
}

function balanceText(isUnpaid: boolean, balance: LeaveBalance | undefined): string {
  if (isUnpaid) return "Unpaid";
  const available = balance ? Number(balance.available_days) : 0;
  return `${available} day${available === 1 ? "" : "s"} left`;
}

export default function LeaveTypePicker({ selected, balanceMap, onSelect }: Props) {
  return (
    <div role="radiogroup" aria-label="Leave type" className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
      {LEAVE_TYPES_LIST.map(type => {
        const isSelected = selected === type.key;
        const balance = balanceMap[type.key];
        const hasCarryForward = !!balance && balance.carried_forward > 0;
        return (
          <button
            key={type.key}
            type="button"
            role="radio"
            aria-checked={isSelected}
            onClick={() => onSelect(type.key)}
            className={`option-card${isSelected ? " option-card--selected" : ""}`}
          >
            <span className="block text-[13px] font-semibold text-[var(--on-bg)]">{type.label}</span>
            <span className={`block text-xs ${isSelected ? "text-[var(--primary)]" : "text-[var(--on-variant)]"}`}>
              {balanceText(type.isLwp, balance)}
            </span>
            {hasCarryForward && (
              <span className="mt-0.5 block text-[11px] text-[var(--on-variant)]">
                {balance?.carry_forward_expiry_date ? `Carry-forward expires ${fmtDate(balance.carry_forward_expiry_date)}` : "Includes carry-forward"}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
