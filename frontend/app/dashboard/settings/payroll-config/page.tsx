"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollSettings } from "@/types/payroll";
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
            className="flex items-center gap-1.5 text-[13px] text-[var(--on-variant)] hover:text-[var(--on-bg)] mb-2 transition-colors"
          >
            <i className="ti ti-arrow-left text-sm" /> Settings
          </button>
          <h1 className="text-[22px] font-bold leading-tight" style={{ color: "var(--on-bg)" }}>Payroll Configuration</h1>
          <p className="text-[13px] mt-0.5" style={{ color: "var(--on-variant)" }}>
            Salary structures, statutory rules, and payroll cycle settings
          </p>
        </div>
        {tab === "run" && hasChanges && (
          <button
            onClick={saveSettings}
            disabled={saving}
            className="btn btn-filled disabled:opacity-50"
          >
            {saving
              ? <><i className="ti ti-loader-2 animate-spin text-sm" /> Saving…</>
              : <><i className="ti ti-device-floppy text-sm" /> Save Settings</>}
          </button>
        )}
      </div>

      {saveMsg && (
        <div className={`alert mb-4 ${saveMsg.startsWith("Failed") ? "alert-error" : "alert-success"}`}>
          {saveMsg}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-5 p-1 rounded-xl w-fit" style={{ background: "var(--bg-mid)" }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-medium transition-all ${
              tab === t.id
                ? "bg-[var(--surface)] text-[var(--primary)] shadow font-semibold"
                : "text-[var(--on-variant)] hover:text-[var(--on-bg)]"
            }`}
          >
            <i className={`ti ${t.icon} text-sm`} /> {t.label}
          </button>
        ))}
      </div>

      {/* ── Payroll Run Settings ── */}
      {tab === "run" && (
        <div className="card">
          <div className="px-5 py-4 border-b border-[var(--outline-v)]">
            <div className="font-semibold" style={{ color: "var(--on-bg)" }}>Payroll Cycle & Approval Settings</div>
            <div className="text-[12px] mt-0.5" style={{ color: "var(--outline)" }}>Controls how payroll cycles are defined, approved and paid</div>
          </div>

          {loading ? (
            <div className="px-5 py-10 text-center text-sm" style={{ color: "var(--outline)" }}>
              <i className="ti ti-loader-2 animate-spin text-lg" />
              <div className="mt-2">Loading settings…</div>
            </div>
          ) : (
            <>
              {/* Cycle dates */}
              <div className="px-5 py-5 border-b border-[var(--outline-v)]">
                <div className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--on-variant)" }}>Salary Cycle</div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Cycle Start Day</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Day of month the cycle begins</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.cycle_start_day ?? ""}
                      onChange={e => set("cycle_start_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Cycle End Day</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Day of month the cycle ends</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.cycle_end_day ?? ""}
                      onChange={e => set("cycle_end_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Pay Day</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Day salary is credited to employees</div>
                    <input
                      type="number"
                      min={1} max={31}
                      value={draft.pay_day ?? ""}
                      onChange={e => set("pay_day", Number(e.target.value))}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                </div>
              </div>

              {/* Approval */}
              <div className="px-5 py-5 border-b border-[var(--outline-v)]">
                <div className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--on-variant)" }}>Approval Workflow</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Attendance Approval Levels</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Who must approve attendance before payroll can run</div>
                    <div className="flex gap-2">
                      {(["L1", "L1_L2"] as const).map(level => (
                        <button
                          key={level}
                          onClick={() => set("approval_levels", level)}
                          className={`flex-1 py-2 rounded-lg text-[12px] font-semibold border transition-all ${
                            draft.approval_levels === level
                              ? "bg-[var(--primary)] text-white border-[var(--primary)]"
                              : "border-[var(--outline-v)] text-[var(--on-variant)] hover:border-[var(--primary-c)]"
                          }`}
                        >
                          {level === "L1" ? "Manager only (L1)" : "Manager + HR (L1 + L2)"}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Employee Query Window (hours)</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>How long employees have to raise payslip queries</div>
                    <input
                      type="number"
                      min={1} max={168}
                      value={draft.employee_query_window_hours ?? ""}
                      onChange={e => set("employee_query_window_hours", Number(e.target.value))}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                </div>
              </div>

              {/* EPF / Statutory Rates */}
              <div className="px-5 py-5 border-b border-[var(--outline-v)]">
                <div className="text-[12px] font-bold uppercase tracking-wider mb-1" style={{ color: "var(--on-variant)" }}>EPF / EDLI Statutory Rates</div>
                <div className="text-[11px] mb-3" style={{ color: "var(--outline)" }}>
                  EPFO-mandated rates. Update here when the law changes — no code change required.
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>EPS Rate (%)</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Employer Pension Scheme contribution</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.eps_rate ?? ""}
                      onChange={e => set("eps_rate", e.target.value)}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>EDLI Rate (%)</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Employees Deposit Linked Insurance</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.edli_rate ?? ""}
                      onChange={e => set("edli_rate", e.target.value)}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>EDLI Wage Ceiling (₹)</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Monthly wage cap for EDLI computation</div>
                    <input
                      type="number" step="1" min={0}
                      value={draft.edli_wage_ceiling ?? ""}
                      onChange={e => set("edli_wage_ceiling", e.target.value)}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                  <div>
                    <label className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>EPF Admin Rate (%)</label>
                    <div className="text-[11px] mb-2" style={{ color: "var(--outline)" }}>Administrative / inspection charges</div>
                    <input
                      type="number" step="0.01" min={0} max={100}
                      value={draft.epf_admin_rate ?? ""}
                      onChange={e => set("epf_admin_rate", e.target.value)}
                      className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2 text-[var(--on-bg)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-c)]"
                    />
                  </div>
                </div>
              </div>

              {/* Optional components */}
              <div className="px-5 py-5">
                <div className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--on-variant)" }}>Optional Payroll Components</div>
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
                <div className="px-5 py-4 border-t border-[var(--outline-v)] flex items-center justify-between" style={{ background: "var(--bg-low)" }}>
                  <span className="text-[12px]" style={{ color: "var(--on-variant)" }}>You have unsaved changes</span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setForm({})}
                      className="btn btn-ghost btn-sm"
                    >
                      Discard
                    </button>
                    <button
                      onClick={saveSettings}
                      disabled={saving}
                      className="btn btn-filled disabled:opacity-50"
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
    <div className="flex items-center justify-between py-3 px-4 rounded-xl" style={{ background: "var(--bg-low)" }}>
      <div>
        <div className="text-[13px] font-semibold" style={{ color: "var(--on-bg)" }}>{label}</div>
        <div className="text-[11px] mt-0.5" style={{ color: "var(--outline)" }}>{description}</div>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${value ? "bg-[var(--primary)]" : "bg-[var(--bg-high)]"}`}
      >
        <span className={`inline-block h-4 w-4 rounded-full shadow transition-transform ${value ? "translate-x-6" : "translate-x-1"}`} style={{ background: "#fff" }} />
      </button>
    </div>
  );
}
