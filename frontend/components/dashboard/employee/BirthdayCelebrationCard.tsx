"use client";

import type { BirthdayEmployee } from "@/types/employeeDashboard";
import { useT } from "@/hooks/useI18n";

function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase() ?? "").join("");
}

interface Props {
  employee: BirthdayEmployee;
  onOpen:   () => void;
}

/**
 * A single "today's birthday" card shown in the Announcements → Celebration
 * view. Reuses the same .card class every other announcement card uses, with
 * a festive accent so it reads as celebratory content rather than a regular post.
 */
export default function BirthdayCelebrationCard({ employee, onOpen }: Props) {
  const t = useT();
  const firstName = employee.full_name.split(" ")[0];

  return (
    <div
      className="card mb-16"
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); } }}
      style={{
        cursor:     "pointer",
        border:     "1px solid rgba(219,39,119,0.25)",
        background: "linear-gradient(135deg, rgba(219,39,119,0.06), rgba(147,51,234,0.05))",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px" }}>
        <div style={{
          width: 44, height: 44, borderRadius: "50%", flexShrink: 0,
          background: "linear-gradient(135deg, #db2777, #9333ea)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 15, fontWeight: 700,
        }}>
          {initials(employee.full_name)}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
              {t("🎂 Happy Birthday {name}", { name: firstName })}
            </span>
            <span className="badge badge-primary" style={{ fontSize: 10 }}>{t("Celebration")}</span>
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
            {t("Today is {name}'s Birthday. Wish {name} a wonderful year ahead.", { name: firstName })}
          </div>
        </div>

        <i className="ti ti-chevron-right" style={{ color: "var(--on-variant)", fontSize: 16, flexShrink: 0 }} />
      </div>
    </div>
  );
}
