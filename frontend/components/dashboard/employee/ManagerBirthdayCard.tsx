"use client";

import { useState } from "react";
import { useMyBirthdayWidgets } from "@/hooks/useEmployeeDashboard";
import { SendWishModal } from "@/components/dashboard/SendWishModal";

// Only shown to direct reports of the manager whose birthday it is today.
export default function ManagerBirthdayCard() {
  const { data, loading } = useMyBirthdayWidgets();
  const manager = data?.manager;
  const [sending, setSending] = useState(false);

  if (loading || !manager) return null;

  return (
    <div className="card mb-16">
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 20px" }}>
        <div style={{
          width: 34, height: 34, borderRadius: 8, flexShrink: 0,
          background: "rgba(147,51,234,0.12)", color: "#9333ea",
          display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16,
        }}>
          <i className="ti ti-cake" />
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "#9333ea", letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 2 }}>
            🎂 Manager Birthday
          </div>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
            Today is your manager&apos;s birthday. Wish {manager.full_name} a wonderful birthday.
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
            {manager.message}
          </div>
        </div>

        <button
          className="btn btn-filled btn-sm"
          style={{ flexShrink: 0 }}
          onClick={() => setSending(true)}
        >
          <i className="ti ti-confetti" /> Send Wishes
        </button>
      </div>

      {sending && (
        <SendWishModal
          employeeId={manager.employee_id}
          employeeName={manager.full_name}
          employeeEmail={manager.email}
          department={manager.department}
          designation={manager.designation}
          preferredKey="birthday"
          onClose={() => setSending(false)}
          onSent={() => setSending(false)}
        />
      )}
    </div>
  );
}
