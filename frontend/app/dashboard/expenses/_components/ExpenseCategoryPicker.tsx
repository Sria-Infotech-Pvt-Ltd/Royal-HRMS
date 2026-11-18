"use client";

import { categoryStyle, tint } from "./expenseView";

export type ExpenseCategory = "travel" | "meals" | "equipment" | "other";

export const CATEGORIES: { value: ExpenseCategory; label: string; icon: string }[] = [
  { value: "travel",    label: "Travel",    icon: "ti-plane-departure"        },
  { value: "meals",     label: "Meals",     icon: "ti-tools-kitchen-2"        },
  { value: "equipment", label: "Equipment", icon: "ti-device-desktop"         },
  { value: "other",     label: "Other",     icon: "ti-dots-circle-horizontal" },
];

interface Props {
  value: ExpenseCategory | "";
  hasError: boolean;
  onChange: (category: ExpenseCategory) => void;
}

/** Tap-a-tile category choice (replaces the drop-down). */
export default function ExpenseCategoryPicker({ value, hasError, onChange }: Props) {
  return (
    <div className="xf-cats" role="radiogroup" aria-label="Expense category">
      {CATEGORIES.map(category => {
        const colour = categoryStyle(category.value).colour;
        const selected = value === category.value;
        return (
          <button
            key={category.value}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`xf-cat${selected ? " is-on" : ""}${hasError && !value ? " is-bad" : ""}`}
            style={selected ? { borderColor: colour, color: colour, background: tint(colour, 0.1), boxShadow: `0 0 0 3px ${tint(colour, 0.16)}` } : undefined}
            onClick={() => onChange(category.value)}
          >
            <span aria-hidden="true" style={{ width: 40, height: 40, borderRadius: 12, display: "grid", placeItems: "center", background: selected ? colour : tint(colour, 0.14), color: selected ? "#fff" : colour, transition: "all .15s ease" }}>
              <i className={`ti ${category.icon}`} style={{ fontSize: 22 }} />
            </span>
            {category.label}
          </button>
        );
      })}
    </div>
  );
}
