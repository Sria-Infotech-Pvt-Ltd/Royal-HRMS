"use client";

import { useState } from "react";
import { useBirthdaysToday } from "@/hooks/useEmployeeDashboard";
import type { BirthdayEmployee } from "@/types/employeeDashboard";
import BirthdayCelebrationModal from "./BirthdayCelebrationModal";

function initials(name: string): string {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

export default function EmpBirthdayAnnouncement() {
  const { data, loading } = useBirthdaysToday();
  const birthdays = data?.birthdays ?? [];
  const [celebrateTarget, setCelebrateTarget] = useState<BirthdayEmployee | null>(null);

  // Hidden entirely while loading or when nobody has a birthday today.
  if (loading || birthdays.length === 0) return null;

  const isSingle = birthdays.length === 1;

  return (
    <>
      <div
        className="mb-16 bday-announce-in"
        role="button"
        tabIndex={0}
        onClick={() => isSingle && setCelebrateTarget(birthdays[0])}
        onKeyDown={e => { if (isSingle && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); setCelebrateTarget(birthdays[0]); } }}
        style={{
          padding: "16px 20px",
          borderRadius: 10,
          background: "linear-gradient(135deg, rgba(219,39,119,0.08), rgba(147,51,234,0.06))",
          border: "1px solid rgba(219,39,119,0.20)",
          cursor: isSingle ? "pointer" : undefined,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: isSingle ? 4 : 10 }}>
          <span style={{ fontSize: 20 }}>🎉</span>
          <span style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
            {isSingle ? `Happy Birthday, ${birthdays[0].full_name}!` : "Today's Birthdays"}
          </span>
        </div>

        {isSingle ? (
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginLeft: 28 }}>
            Wishing you a wonderful year ahead. 🎂
          </div>
        ) : (
          <>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {birthdays.map(b => (
                <div
                  key={b.employee_id}
                  role="button"
                  tabIndex={0}
                  onClick={() => setCelebrateTarget(b)}
                  onKeyDown={e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setCelebrateTarget(b); } }}
                  style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
                >
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                    background: "#db2777", color: "#fff", display: "flex",
                    alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700,
                  }}>
                    {initials(b.full_name)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>🎂 {b.full_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                      {b.designation}{b.department ? ` · ${b.department}` : ""}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 10 }}>
              Wish them a wonderful day!
            </div>
          </>
        )}
      </div>

      {celebrateTarget && (
        <BirthdayCelebrationModal
          employee={celebrateTarget}
          onClose={() => setCelebrateTarget(null)}
        />
      )}
    </>
  );
}
