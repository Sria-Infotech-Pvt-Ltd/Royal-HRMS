"use client";

import { useState } from "react";
import { useMyBirthdayWidgets } from "@/hooks/useEmployeeDashboard";
import { SendWishModal } from "@/components/dashboard/SendWishModal";

// Strictly scoped to the logged-in user's own team (same reporting manager)
// — never surfaces birthdays outside their reporting hierarchy.
export default function TeamBirthdayCard() {
  const { data, loading } = useMyBirthdayWidgets();
  const team = data?.team ?? [];
  const [index, setIndex] = useState(0);
  const [sendingTo, setSendingTo] = useState<number | null>(null);

  if (loading || team.length === 0) return null;

  const person = team[Math.min(index, team.length - 1)];

  return (
    <div className="card mb-16">
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 20px" }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, flexShrink: 0,
          background: "rgba(14,124,134,0.12)", color: "var(--info)",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
        }}>
          <i className="ti ti-cake" />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--info)", letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 2 }}>
            🎂 Team Birthday Today
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
            Today is {person.full_name}&apos;s birthday.
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
            {person.message}
          </div>

          {team.length > 1 && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
              {team.map((t, i) => (
                <button
                  key={t.employee_id}
                  onClick={() => setIndex(i)}
                  aria-label={`Show ${t.full_name}`}
                  style={{
                    width: 7, height: 7, borderRadius: "50%", padding: 0, border: "none", cursor: "pointer",
                    background: i === index ? "var(--info)" : "var(--outline-v)",
                  }}
                />
              ))}
            </div>
          )}
        </div>

        <button
          className="btn btn-filled btn-sm"
          style={{ flexShrink: 0 }}
          onClick={() => setSendingTo(index)}
        >
          <i className="ti ti-confetti" /> Send Wishes
        </button>
      </div>

      {sendingTo !== null && team[sendingTo] && (
        <SendWishModal
          employeeId={team[sendingTo].employee_id}
          employeeName={team[sendingTo].full_name}
          employeeEmail={team[sendingTo].email}
          department={team[sendingTo].department}
          designation={team[sendingTo].designation}
          preferredKey="birthday"
          onClose={() => setSendingTo(null)}
          onSent={() => setSendingTo(null)}
        />
      )}
    </div>
  );
}
