"use client";

import { useRef, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { StatutoryConfig } from "@/types/payroll";

// State model uses integer PK in the backend
interface StateOption { id: number; name: string; code: string; is_active: boolean; }
interface PTSlab { min: number; max: number | null; amount: number; }

export default function StatutoryConfigTab() {
  const { data: configs, loading, refetch } = useFetch<StatutoryConfig[]>(API.payroll.statutory);
  const { data: states } = useFetch<StateOption[]>(API.branches.states);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside a field and releasing past the modal's edge would otherwise land
  // on the overlay and close it mid-input. Only close when the gesture both
  // started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);
  const [newStateId, setNewStateId] = useState("");
  const [draft, setDraft] = useState<Partial<StatutoryConfig>>({});

  const selected = configs?.find(c => c.id === selectedId) ?? null;
  const current: Partial<StatutoryConfig> = { ...selected, ...draft };
  const currentSlabs: PTSlab[] = (current.pt_slabs as PTSlab[] | undefined) ?? [];

  function setField<K extends keyof StatutoryConfig>(key: K, value: StatutoryConfig[K]) {
    setDraft(prev => ({ ...prev, [key]: value }));
  }

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 3000);
  }

  function selectConfig(id: string) {
    setSelectedId(id);
    setDraft({});
  }

  function setSlabs(slabs: PTSlab[]) {
    setDraft(prev => ({ ...prev, pt_slabs: slabs }));
  }

  function addSlab() {
    setSlabs([...currentSlabs, { min: 0, max: null, amount: 0 }]);
  }

  function removeSlab(index: number) {
    setSlabs(currentSlabs.filter((_, i) => i !== index));
  }

  function updateSlab(index: number, field: keyof PTSlab, raw: string) {
    const updated = currentSlabs.map((slab, i) => {
      if (i !== index) return slab;
      if (field === "max") return { ...slab, max: raw === "" ? null : Number(raw) };
      return { ...slab, [field]: Number(raw) };
    });
    setSlabs(updated);
  }

  async function saveConfig() {
    if (!selectedId) return;
    setSaving(true);
    try {
      await clientApi.put(API.payroll.statutoryDetail(selectedId), draft);
      setDraft({});
      refetch();
      flash("Statutory config saved.");
    } catch {
      flash("Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function createConfig() {
    if (!newStateId) return;
    setSaving(true);
    try {
      const res = await clientApi.post<{ data: StatutoryConfig }>(API.payroll.statutory, { state: Number(newStateId) });
      setShowNew(false);
      setNewStateId("");
      refetch();
      setSelectedId(res.data.data.id);
      flash("Config created.");
    } catch {
      flash("A config for this state may already exist.");
    } finally {
      setSaving(false);
    }
  }

  // State.id is an integer; StatutoryConfig.state is also the State integer PK
  const configuredStateIds = new Set((configs ?? []).map(c => Number(c.state)));
  const availableStates = (states ?? []).filter(s => !configuredStateIds.has(s.id));
  const hasChanges = Object.keys(draft).length > 0;

  return (
    <div className="flex gap-4">
      {/* State list */}
      <div className="w-56 shrink-0">
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="font-semibold text-[13px] text-gray-900">States</span>
            {availableStates.length > 0 && (
              <button onClick={() => setShowNew(true)} className="p-1 rounded-lg text-blue-800 hover:bg-blue-50"><i className="ti ti-plus text-sm" /></button>
            )}
          </div>
          {loading ? (
            <div className="px-4 py-6 text-center text-gray-400 text-xs"><i className="ti ti-loader-2 animate-spin" /></div>
          ) : (
            <div className="divide-y divide-gray-100 max-h-96 overflow-y-auto">
              {(configs ?? []).map(c => (
                <button
                  key={c.id}
                  onClick={() => selectConfig(c.id)}
                  className={`w-full text-left px-4 py-3 transition-colors ${selectedId === c.id ? "bg-blue-50" : "hover:bg-gray-50"}`}
                >
                  <div className="font-medium text-[13px] text-gray-900">{c.state_name}</div>
                  <div className="text-[10px] text-gray-400 mt-0.5">{c.state_code}</div>
                </button>
              ))}
              {(configs ?? []).length === 0 && (
                <div className="px-4 py-6 text-center text-gray-400 text-xs">No states configured</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Config panel */}
      <div className="flex-1">
        {msg && (
          <div className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium ${msg.startsWith("Failed") || msg.startsWith("A config") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
            {msg}
          </div>
        )}

        {!selected ? (
          <div className="bg-white rounded-xl border border-gray-200 px-6 py-12 text-center text-gray-400">
            <i className="ti ti-building-bank text-3xl mb-2 block" />
            Select a state to configure statutory deductions (PT, ESI, LWF)
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <span className="font-semibold text-gray-900">{selected.state_name} — Statutory Config</span>
              {hasChanges && (
                <button
                  onClick={saveConfig}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 disabled:opacity-50"
                >
                  {saving ? "Saving…" : <><i className="ti ti-device-floppy text-sm" /> Save</>}
                </button>
              )}
            </div>

            <div className="divide-y divide-gray-100">
              {/* Professional Tax */}
              <Section title="Professional Tax (PT)">
                <ToggleRow
                  label="PT Applicable"
                  value={current.pt_applicable ?? false}
                  onChange={v => setField("pt_applicable", v)}
                />

                {current.pt_applicable && (
                  <div className="mt-4">
                    <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-2">PT Slabs</div>
                    <div className="border border-gray-200 rounded-lg overflow-hidden">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="bg-gray-50 border-b border-gray-200">
                            <th className="px-3 py-2 text-left text-[11px] font-semibold text-gray-500 uppercase">Min (₹)</th>
                            <th className="px-3 py-2 text-left text-[11px] font-semibold text-gray-500 uppercase">Max (₹)</th>
                            <th className="px-3 py-2 text-left text-[11px] font-semibold text-gray-500 uppercase">PT Amount (₹/mo)</th>
                            <th className="px-3 py-2 w-10" />
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                          {currentSlabs.map((slab, i) => (
                            <tr key={i}>
                              <td className="px-3 py-2">
                                <input
                                  type="number"
                                  min={0}
                                  value={slab.min}
                                  onChange={e => updateSlab(i, "min", e.target.value)}
                                  className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                                />
                              </td>
                              <td className="px-3 py-2">
                                <input
                                  type="number"
                                  min={0}
                                  value={slab.max ?? ""}
                                  placeholder="No limit"
                                  onChange={e => updateSlab(i, "max", e.target.value)}
                                  className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                                />
                              </td>
                              <td className="px-3 py-2">
                                <input
                                  type="number"
                                  min={0}
                                  value={slab.amount}
                                  onChange={e => updateSlab(i, "amount", e.target.value)}
                                  className="w-full rounded border border-gray-200 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                                />
                              </td>
                              <td className="px-3 py-2 text-right">
                                <button
                                  onClick={() => removeSlab(i)}
                                  className="text-red-400 hover:text-red-600 transition-colors p-1 rounded"
                                  title="Remove slab"
                                >
                                  <i className="ti ti-trash text-sm" />
                                </button>
                              </td>
                            </tr>
                          ))}
                          {currentSlabs.length === 0 && (
                            <tr>
                              <td colSpan={4} className="px-3 py-4 text-center text-gray-400 text-xs">
                                No PT slabs defined — add one below
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                    <button
                      onClick={addSlab}
                      className="mt-2 flex items-center gap-1.5 text-[12px] text-blue-700 border border-blue-200 hover:bg-blue-50 px-3 py-1.5 rounded-lg transition-colors"
                    >
                      <i className="ti ti-plus text-xs" /> Add Slab
                    </button>
                    <div className="mt-2 text-[11px] text-gray-400">
                      Leave Max blank on the last slab to apply it to all higher incomes.
                    </div>
                  </div>
                )}
              </Section>

              {/* ESI */}
              <Section title="Employee State Insurance (ESI)">
                <ToggleRow
                  label="ESI Applicable"
                  value={current.esi_applicable ?? false}
                  onChange={v => setField("esi_applicable", v)}
                />
                {current.esi_applicable && (
                  <div className="grid grid-cols-3 gap-3 mt-3">
                    <NumField
                      label="Wage Ceiling (₹)"
                      value={String(current.esi_wage_ceiling ?? "")}
                      onChange={v => setField("esi_wage_ceiling", v)}
                    />
                    <NumField
                      label="Employee Rate (%)"
                      value={String(current.esi_employee_rate ?? "")}
                      onChange={v => setField("esi_employee_rate", v)}
                      step="0.01"
                    />
                    <NumField
                      label="Employer Rate (%)"
                      value={String(current.esi_employer_rate ?? "")}
                      onChange={v => setField("esi_employer_rate", v)}
                      step="0.01"
                    />
                  </div>
                )}
              </Section>

              {/* LWF */}
              <Section title="Labour Welfare Fund (LWF)">
                <ToggleRow
                  label="LWF Applicable"
                  value={current.lwf_applicable ?? false}
                  onChange={v => setField("lwf_applicable", v)}
                />
                {current.lwf_applicable && (
                  <>
                    <div className="grid grid-cols-3 gap-3 mt-3">
                      <NumField
                        label="Employee Amount (₹)"
                        value={String(current.lwf_employee_amount ?? "")}
                        onChange={v => setField("lwf_employee_amount", v)}
                      />
                      <NumField
                        label="Employer Amount (₹)"
                        value={String(current.lwf_employer_amount ?? "")}
                        onChange={v => setField("lwf_employer_amount", v)}
                      />
                      <div>
                        <label className="block text-[12px] font-semibold text-gray-700 mb-1">Frequency</label>
                        <select
                          value={current.lwf_frequency ?? "monthly"}
                          onChange={e => setField("lwf_frequency", e.target.value as StatutoryConfig["lwf_frequency"])}
                          className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                        >
                          <option value="monthly">Monthly</option>
                          <option value="halfyearly">Half-yearly</option>
                          <option value="annual">Annual</option>
                        </select>
                      </div>
                    </div>
                    <p className="text-[11px] text-gray-500 mt-2">
                      The amount above is charged in full only in the due month(s) below — it is never divided across the year.
                    </p>
                    {current.lwf_frequency === "annual" && (
                      <div className="grid grid-cols-3 gap-3 mt-3">
                        <MonthSelect
                          label="Due Month"
                          value={current.lwf_due_months?.[0]}
                          onChange={m => setField("lwf_due_months", m ? [m] : [])}
                        />
                      </div>
                    )}
                    {current.lwf_frequency === "halfyearly" && (
                      <div className="grid grid-cols-3 gap-3 mt-3">
                        <MonthSelect
                          label="Due Month 1"
                          value={current.lwf_due_months?.[0]}
                          onChange={m => {
                            const second = current.lwf_due_months?.[1];
                            setField("lwf_due_months", [m, second === m ? undefined : second].filter((x): x is number => typeof x === "number"));
                          }}
                        />
                        <MonthSelect
                          label="Due Month 2"
                          value={current.lwf_due_months?.[1]}
                          onChange={m => {
                            const first = current.lwf_due_months?.[0];
                            setField("lwf_due_months", [first, m].filter((x): x is number => typeof x === "number"));
                          }}
                          disabledMonth={current.lwf_due_months?.[0]}
                        />
                      </div>
                    )}
                  </>
                )}
              </Section>
            </div>
          </div>
        )}
      </div>

      {/* New state modal */}
      {showNew && (
        <div
          className="fixed inset-0 z-[1000] bg-black/40 flex items-center justify-center p-4"
          onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
          onClick={e => mouseDownOnOverlay.current && e.target === e.currentTarget && setShowNew(false)}
        >
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="font-semibold text-gray-900">Add State Config</div>
              <button onClick={() => setShowNew(false)} className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"><i className="ti ti-x" /></button>
            </div>
            <div className="px-6 py-5">
              <label className="block text-[12px] font-semibold text-gray-700 mb-1.5">State</label>
              <select
                value={newStateId}
                onChange={e => setNewStateId(e.target.value)}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                <option value="">Select a state</option>
                {availableStates.map(s => <option key={s.id} value={s.id}>{s.name} ({s.code})</option>)}
              </select>
              <div className="flex items-center justify-end gap-2 mt-4">
                <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100">Cancel</button>
                <button
                  onClick={createConfig}
                  disabled={saving || !newStateId}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-blue-800 text-white rounded-lg hover:bg-blue-900 disabled:opacity-50"
                >
                  {saving ? "Creating…" : "Create Config"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-4">
      <div className="text-[11px] font-bold text-gray-500 uppercase tracking-wider mb-3">{title}</div>
      {children}
    </div>
  );
}

function ToggleRow({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[13px] font-medium text-gray-800">{label}</span>
      <button
        onClick={() => onChange(!value)}
        className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${value ? "bg-blue-800" : "bg-gray-200"}`}
      >
        <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${value ? "translate-x-4" : "translate-x-0.5"}`} />
      </button>
    </div>
  );
}

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function MonthSelect({
  label, value, onChange, disabledMonth,
}: {
  label: string;
  value: number | undefined;
  onChange: (month: number | undefined) => void;
  disabledMonth?: number;
}) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-gray-700 mb-1">{label}</label>
      <select
        value={value ?? ""}
        onChange={e => onChange(e.target.value ? Number(e.target.value) : undefined)}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
      >
        <option value="">Select month</option>
        {MONTH_NAMES.map((name, i) => (
          <option key={name} value={i + 1} disabled={disabledMonth === i + 1}>{name}</option>
        ))}
      </select>
    </div>
  );
}

function NumField({ label, value, onChange, step }: { label: string; value: string; onChange: (v: string) => void; step?: string }) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-gray-700 mb-1">{label}</label>
      <input
        type="number"
        step={step ?? "1"}
        min={0}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
      />
    </div>
  );
}
