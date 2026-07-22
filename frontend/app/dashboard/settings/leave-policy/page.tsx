"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import PolicyTab from "./_components/PolicyTab";
import CreditTab from "./_components/CreditTab";
import LeavePoliciesTab from "./_components/LeavePoliciesTab";
import CarryForwardTab from "./_components/CarryForwardTab";

type Tab = "types" | "policies" | "credit" | "carryForward";

// Carry Forward is an execution/audit action (system_admin, hr_admin, hr only)
// — kept out of the employee-visible tab bar even though this whole settings
// page already requires settings.view at the route level.
const CARRY_FORWARD_ROLES = ["system_admin", "hr_admin", "hr"];

const BASE_TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "types",    icon: "ti-beach",      label: "Leave Types"  },
  { id: "policies", icon: "ti-settings-2", label: "Leave Policy" },
  { id: "credit",   icon: "ti-coin",       label: "Credit Rules" },
];

export default function LeavePolicyPage() {
  const router = useRouter();
  const user = useCurrentUser();
  const [tab, setTab] = useState<Tab>("types");

  const canCarryForward = !!user && CARRY_FORWARD_ROLES.includes(user.role);
  const TABS = canCarryForward
    ? [...BASE_TABS, { id: "carryForward" as Tab, icon: "ti-repeat", label: "Carry Forward" }]
    : BASE_TABS;

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

      {tab === "types"        && <PolicyTab />}
      {tab === "policies"     && <LeavePoliciesTab />}
      {tab === "credit"       && <CreditTab />}
      {tab === "carryForward" && canCarryForward && <CarryForwardTab />}
    </>
  );
}
