// Small presentational building blocks shared by EmployeeDrawer.tsx — split
// out purely to keep that file under this codebase's ~300-line guideline.
"use client";

import type { ReactNode } from "react";

export const STATUS_BADGE: Record<string, string> = {
  Active: "badge-success",
  "Notice Period": "badge-warn",
  Onboarding: "badge-info",
  Exited: "badge-neutral",
};

/** Boxed, labelled section — the record's fields are grouped into these
    cards (two per row on wide screens) rather than one long stacked list. */
export function SectionCard({ icon, title, children }: { icon: string; title: string; children: ReactNode }) {
  return (
    <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "14px 16px", marginBottom: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 11, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", marginBottom: 12 }}>
        <i className={`ti ${icon}`} /> {title}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>{children}</div>
    </div>
  );
}

/** One label/value line within a SectionCard — label left, bold value right. */
export function Row({ label, value, valueNode, mono }: {
  label: string; value?: string | null; valueNode?: ReactNode; mono?: boolean;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
      <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 700, textAlign: "right", fontFamily: mono ? "Menlo, Consolas, monospace" : undefined }}>
        {valueNode ?? (value || "—")}
      </div>
    </div>
  );
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
