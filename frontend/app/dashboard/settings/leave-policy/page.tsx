"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import PolicyTab from "./_components/PolicyTab";
import CreditTab from "./_components/CreditTab";

type Tab = "policy" | "credit";

const TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "policy", icon: "ti-beach",  label: "Leave Policy"  },
  { id: "credit", icon: "ti-coin",   label: "Credit Rules"  },
];

export default function LeavePolicyPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("policy");

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Leave Management</div>
          <div className="page-sub">Configure leave types, entitlements and balance crediting</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 24, borderBottom: "1px solid var(--outline-v)", paddingBottom: 0 }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              display: "flex", alignItems: "center", gap: 7,
              padding: "10px 18px", fontSize: 13, fontWeight: 600,
              background: "none", border: "none", cursor: "pointer",
              borderBottom: tab === t.id ? "2px solid var(--primary)" : "2px solid transparent",
              color: tab === t.id ? "var(--primary)" : "var(--on-variant)",
              marginBottom: -1, transition: "color 0.15s",
            }}
          >
            <i className={`ti ${t.icon}`} style={{ fontSize: 15 }} />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "policy" && <PolicyTab />}
      {tab === "credit" && <CreditTab />}
    </>
  );
}
