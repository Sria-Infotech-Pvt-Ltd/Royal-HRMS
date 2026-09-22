// Small presentational building blocks shared by EmployeeDrawer.tsx — split
// out purely to keep that file under this codebase's ~300-line guideline.
"use client";

export const STATUS_BADGE: Record<string, string> = {
  Active: "badge-success",
  "Notice Period": "badge-warn",
  Onboarding: "badge-info",
  Exited: "badge-neutral",
};

export function SectionTitle({ icon, title }: { icon: string; title: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", marginTop: 22, marginBottom: 12 }}>
      <i className={`ti ${icon}`} /> {title}
    </div>
  );
}

export function Field({ label, value, mono }: { label: string; value: string | null | undefined; mono?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{label}</div>
      <div style={{ fontSize: 13, fontFamily: mono ? "Menlo, Consolas, monospace" : undefined }}>{value || "—"}</div>
    </div>
  );
}

export function PillField({ label, value, badgeClass }: { label: string; value: string | null | undefined; badgeClass: string }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{label}</div>
      <div style={{ marginTop: 2 }}>
        {value ? <span className={`badge ${badgeClass}`}>{value}</span> : <span style={{ fontSize: 13 }}>—</span>}
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
