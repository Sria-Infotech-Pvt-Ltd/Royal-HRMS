"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import PolicyTab from "./_components/PolicyTab";
import CreditTab from "./_components/CreditTab";
import LeavePoliciesTab from "./_components/LeavePoliciesTab";
import CarryForwardTab from "./_components/CarryForwardTab";
import MonthlyLeaveTab from "./_components/MonthlyLeaveTab";
import OpeningBalanceImportModal from "./_components/OpeningBalanceImportModal";

type Tab = "types" | "policies" | "credit" | "carryForward" | "monthly";


const BASE_TABS: { id: Tab; icon: string; label: string }[] = [
  { id: "types",    icon: "ti-beach",      label: "Leave Types"  },
  { id: "policies", icon: "ti-settings-2", label: "Leave Policy" },
  { id: "credit",   icon: "ti-coin",       label: "Credit Rules" },
];

export default function LeavePolicyPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("types");
  const [showImportModal, setShowImportModal] = useState(false);

  const isLeaveAdmin = usePermission("leave.edit");
  // Monthly credits change individual balances, so they follow the Leave
  // Credits permission (leave.approve); the backend also enforces per-employee scope.
  const canManageCredits = usePermission("leave.approve");
  const TABS = [
    ...BASE_TABS,
    ...(isLeaveAdmin ? [{ id: "carryForward" as Tab, icon: "ti-repeat", label: "Carry Forward" }] : []),
    ...(canManageCredits ? [{ id: "monthly" as Tab, icon: "ti-calendar-plus", label: "Monthly Leave Management" }] : []),
  ];

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Leave Management</div>
          <div className="page-sub">Configure leave types, entitlements and balance crediting</div>
        </div>
        <div className="page-actions">
          {isLeaveAdmin && (
            <button className="btn btn-ghost" onClick={() => setShowImportModal(true)}>
              <i className="ti ti-file-upload" /> Import Opening Balances
            </button>
          )}
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
      {tab === "monthly"      && canManageCredits && <MonthlyLeaveTab />}
      {tab === "carryForward" && isLeaveAdmin && <CarryForwardTab />}

      {showImportModal && (
        <OpeningBalanceImportModal
          onClose={() => setShowImportModal(false)}
          onSuccess={() => showToast("Opening leave balances imported.", "success")}
        />
      )}
    </>
  );
}
