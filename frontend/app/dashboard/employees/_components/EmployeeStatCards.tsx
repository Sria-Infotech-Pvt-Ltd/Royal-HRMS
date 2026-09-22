"use client";

import type { ReactNode } from "react";

export interface EmployeeStatCard {
  label: string;
  value: number;
  icon: string;
  tint: "primary" | "success" | "warn" | "error";
  sub: ReactNode;
  /** Tints the .sub caption text — matches the reference's .sub.w (warn) / .sub.c (crit) modifiers. */
  subTone?: "warn" | "crit";
  /** Jumps the table below straight to this status in one click — set to the
      matching status filter (or "all" to clear it), rather than making the
      user open the status dropdown themselves. */
  onClick?: () => void;
}

const TINT_CLASS: Record<EmployeeStatCard["tint"], string> = {
  primary: "brand",
  success: "ok",
  warn:    "warn",
  error:   "crit",
};

interface Props {
  stats: EmployeeStatCard[];
}

export default function EmployeeStatCards({ stats }: Props) {
  return (
    <div className="stats">
      {stats.map(st => (
        <div
          key={st.label}
          className="stat"
          role={st.onClick ? "button" : undefined}
          tabIndex={st.onClick ? 0 : undefined}
          onClick={st.onClick}
          style={st.onClick ? { cursor: "pointer" } : undefined}
        >
          <div className="top">
            <div className="lbl">{st.label}</div>
            <div className={`ico ${TINT_CLASS[st.tint]}`}>
              <i className={`ti ${st.icon}`} style={{ fontSize: 14 }} />
            </div>
          </div>
          <div className="metricline">
            <div className="num">{st.value}</div>
            <div className={`sub${st.subTone === "warn" ? " w" : st.subTone === "crit" ? " c" : ""}`}>{st.sub}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
