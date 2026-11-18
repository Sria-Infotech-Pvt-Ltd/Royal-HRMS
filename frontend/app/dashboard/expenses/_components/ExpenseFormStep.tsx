"use client";

// One numbered step of the expense claim form: a purple number, a title, an optional hint, then the fields.

import type { ReactNode } from "react";
import { EXPENSE_COLOUR, tint } from "./expenseView";

interface Props { number: number; title: string; hint?: string; done?: boolean; children: ReactNode }

export default function ExpenseFormStep({ number, title, hint, done = false, children }: Props) {
  const colour = done ? EXPENSE_COLOUR.approved : EXPENSE_COLOUR.brand;
  return (
    <section aria-label={title} style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
        <span aria-hidden="true" style={{ width: 24, height: 24, borderRadius: "50%", display: "grid", placeItems: "center", fontSize: 12, fontWeight: 800, background: tint(colour, 0.14), color: colour, transition: "all .2s ease" }}>
          {done ? <i className="ti ti-check" /> : number}
        </span>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>{title}</div>
          {hint && <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{hint}</div>}
        </div>
      </div>
      {children}
    </section>
  );
}
