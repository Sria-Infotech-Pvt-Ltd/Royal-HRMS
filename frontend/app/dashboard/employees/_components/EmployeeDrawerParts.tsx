// Small presentational building blocks shared by EmployeeDrawer.tsx — split
// out purely to keep that file under this codebase's ~300-line guideline.
"use client";

import type { ReactNode } from "react";

/** Status chip colours, as the reference's STATUS_CHIP map. */
export const STATUS_CHIP: Record<string, string> = {
  Active: "ok",
  Onboarding: "warn",
  Probation: "brand",
  "Notice Period": "crit",
  Exited: "",
};

/** Boxed, titled section of the record — the reference's `.rvcard`. Key/value
    rows go in a `.kvlist`; pass `list={false}` for free-form content. `icon`
    is optional (e.g. the Candidate Review onboarding drawer's section
    headers) — omit it for the reference's plain uppercase-title style. */
export function SectionCard({ icon, title, children, list = true }: { icon?: string; title: string; children: ReactNode; list?: boolean }) {
  return (
    <div className="rvcard">
      <h4>{icon && <i className={`ti ${icon}`} />} {title.toUpperCase()}</h4>
      {list ? <div className="kvlist">{children}</div> : children}
    </div>
  );
}

/** One label/value line within a SectionCard — label left, bold value right. */
export function Row({ label, value, valueNode, mono }: {
  label: string; value?: string | null; valueNode?: ReactNode; mono?: boolean;
}) {
  return (
    <div className="kv">
      <span>{label}</span>
      <b style={mono ? { fontFamily: "Menlo, Consolas, monospace" } : undefined}>{valueNode ?? (value || "—")}</b>
    </div>
  );
}

/** 'male' / 'single' -> 'Male' / 'Single' (the API stores these lower-case). */
export function titleCase(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

/** Whole years between an ISO date-of-birth and today. */
export function ageYears(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const dob = new Date(iso);
  if (Number.isNaN(dob.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - dob.getFullYear();
  const monthDiff = now.getMonth() - dob.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < dob.getDate())) age--;
  return age;
}
