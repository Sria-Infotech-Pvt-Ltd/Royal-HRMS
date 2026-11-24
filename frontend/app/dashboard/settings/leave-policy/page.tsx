"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useT } from "@/hooks/useI18n";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import PolicyTab from "./_components/PolicyTab";
import CreditTab from "./_components/CreditTab";
import LeavePoliciesTab from "./_components/LeavePoliciesTab";
import CarryForwardTab from "./_components/CarryForwardTab";
import OpeningBalanceImportModal from "./_components/OpeningBalanceImportModal";
import AttendancePageTabs from "@/app/dashboard/attendance/_components/AttendancePageTabs";

type Tab = "types" | "policies" | "credit" | "carryForward";


export default function LeavePolicyPage() {
  const t = useT();
  const router = useRouter();
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("types");
  const [showImportModal, setShowImportModal] = useState(false);

  const isLeaveAdmin = usePermission("leave.edit");
  const BASE_TABS: { id: Tab; icon: string; label: string }[] = [
    { id: "types",    icon: "ti-beach",      label: t("Leave Types")  },
    { id: "policies", icon: "ti-settings-2", label: t("Leave Policy") },
    { id: "credit",   icon: "ti-coin",       label: t("Credit Rules") },
  ];
  const TABS = isLeaveAdmin
    ? [...BASE_TABS, { id: "carryForward" as Tab, icon: "ti-repeat", label: t("Carry Forward") }]
    : BASE_TABS;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Leave Management")}</div>
          <div className="page-sub">{t("Configure leave types, entitlements and balance crediting")}</div>
        </div>
        <div className="page-actions">
          {isLeaveAdmin && (
            <button className="btn btn-ghost" onClick={() => setShowImportModal(true)}>
              <i className="ti ti-file-upload" /> {t("Import Opening Balances")}
            </button>
          )}
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> {t("Back")}
          </button>
        </div>
      </div>

      <AttendancePageTabs tabs={TABS} active={tab} onSelect={id => setTab(id as Tab)} />

      {tab === "types"        && <PolicyTab />}
      {tab === "policies"     && <LeavePoliciesTab />}
      {tab === "credit"       && <CreditTab />}
      {tab === "carryForward" && isLeaveAdmin && <CarryForwardTab />}

      {showImportModal && (
        <OpeningBalanceImportModal
          onClose={() => setShowImportModal(false)}
          onSuccess={() => showToast(t("Opening leave balances imported."), "success")}
        />
      )}
    </>
  );
}
