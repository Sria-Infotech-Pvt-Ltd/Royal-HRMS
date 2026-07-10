"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import RulesTable, { EARNING_RULES, DEDUCTION_RULES, TYPE_BADGE, PayrollRule, RuleType } from "./_components/RulesTable";

type TabId = "earnings" | "deductions" | "run";
interface EditState { rule: PayrollRule; draft: PayrollRule; }

const RUN_FIELDS = [
  { label: "Pay Frequency",         desc: "How often payroll is run",                  type: "select", opts: ["Monthly","Bi-weekly","Weekly"],                                    val: "Monthly"      },
  { label: "Payroll Lock Date",      desc: "Day of month payroll gets locked",          type: "number",                                                                            val: "25"           },
  { label: "Pay Day",               desc: "Day salaries are disbursed",                 type: "number",                                                                            val: "28"           },
  { label: "ESI Ceiling (Gross ₹)", desc: "Employees above this are ESI exempt",        type: "number",                                                                            val: "21000"        },
  { label: "PT State",              desc: "State for Professional Tax calculation",      type: "select", opts: ["Karnataka","Maharashtra","Tamil Nadu","Telangana","West Bengal"],  val: "Karnataka"    },
  { label: "LOP Calculation",       desc: "Days basis for per-day LOP deduction",        type: "select", opts: ["Calendar Days","Working Days","26 Days Fixed"],                   val: "Working Days" },
  { label: "Auto-approve Threshold",desc: "Net salary below this auto-approves payroll", type: "number",                                                                           val: "0"            },
  { label: "Employer PF %",         desc: "Employer's PF contribution rate",             type: "number",                                                                           val: "12"           },
] as const;

const TABS: { id: TabId; icon: string; label: string }[] = [
  { id: "earnings",   icon: "ti-cash",          label: "Earnings Rules"        },
  { id: "deductions", icon: "ti-minus-vertical", label: "Deduction Rules"       },
  { id: "run",        icon: "ti-settings",       label: "Payroll Run Settings"  },
];

export default function PayrollConfigPage() {
  const router  = useRouter();
  const [tab,     setTab]     = useState<TabId>("earnings");
  const [earning, setEarning] = useState<PayrollRule[]>(EARNING_RULES);
  const [deduct,  setDeduct]  = useState<PayrollRule[]>(DEDUCTION_RULES);
  const [editing, setEditing] = useState<EditState | null>(null);
  const [saving,  setSaving]  = useState(false);

  const active = tab === "earnings" ? earning : deduct;
  const countEnabled    = (arr: PayrollRule[]) => arr.filter(r => r.enabled).length;
  const countStatutory  = (arr: PayrollRule[]) => arr.filter(r => r.statutory).length;

  function toggleRule(setter: React.Dispatch<React.SetStateAction<PayrollRule[]>>) {
    return (id: string) => setter(prev => prev.map(r => r.id === id ? { ...r, enabled: !r.enabled } : r));
  }

  function saveEdit() {
    if (!editing) return;
    setSaving(true);
    setTimeout(() => {
      const update = (prev: PayrollRule[]) => prev.map(r => r.id === editing.rule.id ? editing.draft : r);
      if (tab === "earnings") setEarning(update);
      else setDeduct(update);
      setSaving(false);
      setEditing(null);
    }, 350);
  }

  const STATS = [
    { icon: "ti-cash",          color: "text-blue-800",    bg: "bg-blue-50",    label: "Earning Components", value: earning.length },
    { icon: "ti-minus-vertical",color: "text-red-600",     bg: "bg-red-50",     label: "Deduction Rules",    value: deduct.length  },
    { icon: "ti-shield-check",  color: "text-emerald-700", bg: "bg-emerald-50", label: "Statutory Rules",    value: countStatutory(earning) + countStatutory(deduct) },
    { icon: "ti-toggle-right",  color: "text-violet-700",  bg: "bg-violet-50",  label: "Active Rules",       value: countEnabled(earning) + countEnabled(deduct) },
  ];

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <button onClick={() => router.push("/dashboard/settings")} className="flex items-center gap-1.5 text-[13px] text-gray-500 hover:text-gray-800 mb-2 transition-colors">
            <i className="ti ti-arrow-left text-sm" /> Settings
          </button>
          <h1 className="text-[22px] font-bold text-gray-900 leading-tight">Payroll Rules</h1>
          <p className="text-[13px] text-gray-500 mt-0.5">Configure salary components, statutory deductions and payroll run behaviour</p>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors">
          <i className="ti ti-device-floppy text-sm" /> Save All Changes
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {STATS.map(s => (
          <div key={s.label} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg ${s.bg} flex items-center justify-center shrink-0`}>
              <i className={`ti ${s.icon} ${s.color} text-lg`} />
            </div>
            <div>
              <div className={`text-2xl font-bold ${s.color}`}>{s.value}</div>
              <div className="text-[11px] text-gray-500">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-xl w-fit">
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

      {/* Earnings / Deductions table */}
      {(tab === "earnings" || tab === "deductions") && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <i className={`ti ${tab === "earnings" ? "ti-cash text-blue-800" : "ti-minus-vertical text-red-600"} text-lg`} />
              <span className="font-semibold text-gray-900">{tab === "earnings" ? "Earnings Components" : "Deduction Rules"}</span>
              <span className="text-[11px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-semibold">
                {active.length} rules · {countEnabled(active)} active
              </span>
            </div>
            <span className="text-[12px] text-gray-400">Toggle to enable/disable · Edit icon to configure</span>
          </div>
          <RulesTable
            rules={active}
            onToggle={tab === "earnings" ? toggleRule(setEarning) : toggleRule(setDeduct)}
            onEdit={r => setEditing({ rule: r, draft: { ...r } })}
          />
        </div>
      )}

      {/* Payroll Run Settings */}
      {tab === "run" && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <div className="font-semibold text-gray-900">Payroll Run Configuration</div>
            <div className="text-[12px] text-gray-400 mt-0.5">Controls how payroll is processed each cycle</div>
          </div>
          <div className="grid grid-cols-2 divide-x divide-y divide-gray-100">
            {RUN_FIELDS.map(f => (
              <div key={f.label} className="px-5 py-4">
                <label className="block text-[12px] font-semibold text-gray-700 mb-0.5">{f.label}</label>
                <div className="text-[11px] text-gray-400 mb-2">{f.desc}</div>
                {f.type === "select" ? (
                  <select defaultValue={f.val} className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300">
                    {"opts" in f && f.opts.map((o: string) => <option key={o}>{o}</option>)}
                  </select>
                ) : (
                  <input type="number" defaultValue={f.val} className="w-full rounded-lg border border-gray-200 text-sm px-3 py-2 text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                )}
              </div>
            ))}
          </div>
          <div className="px-5 py-4 border-t border-gray-100 bg-gray-50 flex justify-end">
            <button className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors">
              <i className="ti ti-device-floppy text-sm" /> Save Run Settings
            </button>
          </div>
        </div>
      )}

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-[1000] bg-black/40 flex items-center justify-center p-4" onClick={e => e.target === e.currentTarget && setEditing(null)}>
          <div className="bg-white rounded-2xl w-full max-w-md shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="font-semibold text-gray-900">Edit Rule — {editing.draft.name}</div>
              <button onClick={() => setEditing(null)} className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"><i className="ti ti-x" /></button>
            </div>
            <div className="px-6 py-5 flex flex-col gap-4">
              <div>
                <label className="block text-[12px] font-semibold text-gray-600 mb-1.5">Calculation Type</label>
                <div className="grid grid-cols-4 gap-2">
                  {(["percent","fixed","slab","variable"] as RuleType[]).map(t => (
                    <button
                      key={t}
                      onClick={() => setEditing(p => p ? { ...p, draft: { ...p.draft, type: t } } : p)}
                      className={`py-1.5 rounded-lg text-[11px] font-semibold border transition-all ${editing.draft.type === t ? "bg-blue-800 text-white border-blue-800" : "border-gray-200 text-gray-600 hover:border-blue-300"}`}
                    >
                      {TYPE_BADGE[t].label}
                    </button>
                  ))}
                </div>
              </div>
              {(editing.draft.type === "percent" || editing.draft.type === "fixed") && (
                <div>
                  <label className="block text-[12px] font-semibold text-gray-600 mb-1.5">
                    {editing.draft.type === "percent" ? "Percentage (%)" : "Fixed Amount (₹)"}
                  </label>
                  <input
                    type="number"
                    value={editing.draft.value}
                    onChange={e => setEditing(p => p ? { ...p, draft: { ...p.draft, value: Number(e.target.value) } } : p)}
                    step={editing.draft.type === "percent" ? "0.01" : "1"}
                    min={0}
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  />
                </div>
              )}
              <div>
                <label className="block text-[12px] font-semibold text-gray-600 mb-1.5">Effective Date</label>
                <input
                  type="date"
                  value={editing.draft.effectiveDate}
                  onChange={e => setEditing(p => p ? { ...p, draft: { ...p.draft, effectiveDate: e.target.value } } : p)}
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                />
              </div>
              <div className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg">
                <span className="text-[13px] font-medium text-gray-700">Enable this rule</span>
                <button
                  onClick={() => setEditing(p => p ? { ...p, draft: { ...p.draft, enabled: !p.draft.enabled } } : p)}
                  className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${editing.draft.enabled ? "bg-blue-800" : "bg-gray-200"}`}
                >
                  <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${editing.draft.enabled ? "translate-x-4" : "translate-x-0.5"}`} />
                </button>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-100 bg-gray-50 rounded-b-2xl">
              <button onClick={() => setEditing(null)} className="px-4 py-2 text-sm font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors">Cancel</button>
              <button onClick={saveEdit} disabled={saving} className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 transition-colors disabled:opacity-50">
                {saving ? <><i className="ti ti-loader-2 animate-spin text-sm" /> Saving…</> : <><i className="ti ti-check text-sm" /> Save Rule</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
