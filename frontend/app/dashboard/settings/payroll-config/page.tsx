"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollSettings, SalaryStructureListItem, StatutoryConfig, BranchPayrollConfig } from "@/types/payroll";
import SalaryStructuresTab from "./_components/SalaryStructuresTab";
import StatutoryConfigTab from "./_components/StatutoryConfigTab";
import BranchConfigTab from "./_components/BranchConfigTab";

type TabId = "run" | "structures" | "statutory" | "branch";

const TABS: { id: TabId; icon: string; label: string }[] = [
  { id: "run",       icon: "ti-settings",     label: "Payroll Run Settings"  },
  { id: "structures",icon: "ti-stack",         label: "Salary Structures"     },
  { id: "statutory", icon: "ti-building-bank", label: "Statutory Config"      },
  { id: "branch",    icon: "ti-building",      label: "Branch Config"         },
];

export default function PayrollConfigPage() {
  const router  = useRouter();
  const [tab,   setTab]   = useState<TabId>("run");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);

  const { data: settings, loading, refetch } = useFetch<PayrollSettings>(API.payroll.settings);

  const [form, setForm] = useState<Partial<PayrollSettings>>({});
  const draft: Partial<PayrollSettings> = { ...settings, ...form };

  function set<K extends keyof PayrollSettings>(key: K, value: PayrollSettings[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  async function saveSettings() {
    setSaving(true);
    setSaveMsg(null);
    try {
      await clientApi.put(API.payroll.settings, form);
      setSaveMsg("Settings saved.");
      setForm({});
      refetch();
    } catch {
      setSaveMsg("Failed to save. Please try again.");
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  }

  const hasChanges = Object.keys(form).length > 0;

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button
            onClick={() => router.push("/dashboard/settings")}
            className="flex items-center gap-1.5 text-[13px] text-gray-500 hover:text-gray-800 mb-2 transition-colors"
          >
            <i className="ti ti-arrow-left text-sm" /> Settings
          </button>
          <h1 className="text-[22px] font-bold text-gray-900 leading-tight">Payroll Configuration</h1>
          <p className="text-[13px] text-gray-500 mt-0.5">
            Salary structures, statutory rules, and payroll cycle settings
          </p>
        </div>
        {tab === "run" && hasChanges && (
          <button
            onClick={saveSettings}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors disabled:opacity-50"
          >
            {saving
              ? <><i className="ti ti-loader-2 animate-spin text-sm" /> Saving…</>
              : <><i className="ti ti-device-floppy text-sm" /> Save Settings</>}
          </button>
        )}
      </div>

      {saveMsg && (
        <div className={`mb-4 px-4 py-2.5 rounded-lg text-sm font-medium ${saveMsg.startsWith("Failed") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {saveMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-all ${
              tab === t.id ? "bg-white shadow text-blue-800 font-semibold" : "text-gray-500 hover:text-gray-800"
            }`}
          >
            <i className={`ti ${t.icon} text-sm`} /> {t.label}
          </button>
        ))}
      </div>

      {/* ── Payroll Run Settings ── */}
      {tab === "run" && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <div className="font-semibold text-gray-900">Payroll Cycle & Approval Settings</div>
            <div className="text-[12px] text-gray-400 mt-0.5">Controls how payroll cycles are defined, approved and paid</div>
          </div>

          {loading ? (
            <div className="px-5 py-10 text-center text-gray-400 text-sm">
              <i className="ti ti-loader-2 animate-spin text-lg" />
              <div className="mt-2">Loading settings…</div>
            </div>
          ) : (
            <>
              {/* Cycle dates */}
              <div className="px-5 py-5 border-b border-gray-100">
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-3">Salary Cycle</div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">Cycle Start Day</label>
                    <div className="text-[11px] text-gray-400 mb-2">Day of month the cycle begins</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.cycle_start_day ?? ""}
                      onChange={e => set("cycle_start_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">Cycle End Day</label>
                    <div className="text-[11px] text-gray-400 mb-2">Day of month the cycle ends</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.cycle_end_day ?? ""}
                      onChange={e => set("cycle_end_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">Pay Day</label>
                    <div className="text-[11px] text-gray-400 mb-2">Day salary is credited to employees</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.pay_day ?? ""}
                      onChange={e => set("pay_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                </div>
              </div>

              {/* Approval */}
              <div className="px-5 py-5 border-b border-gray-100">
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-3">Approval Workflow</div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">Attendance Approval Levels</label>
                    <div className="text-[11px] text-gray-400 mb-2">Who must approve attendance before payroll can run</div>
                    <div className="flex gap-2">
                      {(["L1", "L1_L2"] as const).map(level => (
                        <button
                          key={level}
                          onClick={() => set("approval_levels", level)}
                          className={`flex-1 py-2 rounded-lg text-[12px] font-semibold border transition-all ${
                            draft.approval_levels === level
                              ? "bg-blue-800 text-white border-blue-800"
                              : "border-gray-200 text-gray-600 hover:border-blue-300"
                          }`}
                        >
                          {level === "L1" ? "Manager only (L1)" : "Manager + HR (L1 + L2)"}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">Employee Query Window (hours)</label>
                    <div className="text-[11px] text-gray-400 mb-2">How long employees have to raise payslip queries</div>
                    <input
                      type="number"
                      min={1} max={168}
                      value={draft.employee_query_window_hours ?? ""}
                      onChange={e => set("employee_query_window_hours", Number(e.target.value))}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                </div>
              </div>

              {/* EPF / Statutory Rates */}
              <div className="px-5 py-5 border-b border-gray-100">
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-1">EPF / EDLI Statutory Rates</div>
                <div className="text-[11px] text-gray-400 mb-3">
                  EPFO-mandated rates. Update here when the law changes — no code change required.
                </div>
                <div className="grid grid-cols-4 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">EPS Rate (%)</label>
                    <div className="text-[11px] text-gray-400 mb-2">Employer Pension Scheme contribution</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.eps_rate ?? ""}
                      onChange={e => set("eps_rate", e.target.value)}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">EDLI Rate (%)</label>
                    <div className="text-[11px] text-gray-400 mb-2">Employees Deposit Linked Insurance</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.edli_rate ?? ""}
                      onChange={e => set("edli_rate", e.target.value)}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">EDLI Wage Ceiling (₹)</label>
                    <div className="text-[11px] text-gray-400 mb-2">Monthly wage cap for EDLI computation</div>
                    <input
                      type="number" step="1" min={0}
                      value={draft.edli_wage_ceiling ?? ""}
                      onChange={e => set("edli_wage_ceiling", e.target.value)}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold text-gray-700 mb-1">EPF Admin Rate (%)</label>
                    <div className="text-[11px] text-gray-400 mb-2">Administrative / inspection charges</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.epf_admin_rate ?? ""}
                      onChange={e => set("epf_admin_rate", e.target.value)}
                      className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                    />
                  </div>
                </div>
              </div>

              {/* Optional components */}
              <div className="px-5 py-5">
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-3">Optional Payroll Components</div>
                <div className="flex flex-col gap-3">
                  <Toggle
                    label="Reimbursements"
                    description="Show reimbursements step in payroll wizard and include in payslips"
                    value={draft.enable_reimbursements ?? false}
                    onChange={v => set("enable_reimbursements", v)}
                  />
                  <Toggle
                    label="Bonuses"
                    description="Show bonus step in payroll wizard and include in payslips"
                    value={draft.enable_bonuses ?? false}
                    onChange={v => set("enable_bonuses", v)}
                  />
                </div>
              </div>

              {hasChanges && (
                <div className="px-5 py-4 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
                  <span className="text-[12px] text-gray-500">You have unsaved changes</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setForm({})}
                      className="px-3 py-1.5 text-[12px] font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100"
                    >
                      Discard
                    </button>
                    <button
                      onClick={saveSettings}
                      disabled={saving}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 disabled:opacity-50"
                    >
                      {saving ? "Saving…" : "Save Settings"}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {tab === "structures" && <SalaryStructuresTab />}
      {tab === "statutory"  && <StatutoryConfigTab />}
      {tab === "branch"     && <BranchConfigTab />}
    </>
  );
}

// ── Reusable toggle row ────────────────────────────────────────────────────────

function Toggle({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-xl">
      <div>
        <div className="text-[13px] font-semibold text-gray-800">{label}</div>
        <div className="text-[11px] text-gray-400 mt-0.5">{description}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${value ? "bg-blue-800" : "bg-gray-200"}`}
      >
        <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${value ? "translate-x-6" : "translate-x-1"}`} />
      </button>
    </div>
  );
}
