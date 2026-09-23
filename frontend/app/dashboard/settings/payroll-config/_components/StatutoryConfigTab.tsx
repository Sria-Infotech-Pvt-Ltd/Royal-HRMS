"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { StatutoryConfig } from "@/types/payroll";
import { Section, ToggleRow, MonthSelect, NumField } from "./statutoryFormFields";
import PtSlabsEditor, { type PTSlab } from "./PtSlabsEditor";
import NewStatutoryConfigModal from "./NewStatutoryConfigModal";

// State model uses integer PK in the backend
interface StateOption { id: number; name: string; code: string; is_active: boolean; }

export default function StatutoryConfigTab() {
  const { data: configs, loading, refetch } = useFetch<StatutoryConfig[]>(API.payroll.statutory);
  const { data: states } = useFetch<StateOption[]>(API.branches.states);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
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
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--outline-v)]">
            <span className="font-semibold text-[13px] text-[var(--on-bg)]">States</span>
            {availableStates.length > 0 && (
              <button onClick={() => setShowNew(true)} className="p-1 rounded-lg text-[var(--info)] hover:bg-[var(--info-c)]"><i className="ti ti-plus text-sm" /></button>
            )}
          </div>
          {loading ? (
            <div className="px-4 py-6 text-center text-[var(--outline)] text-xs"><i className="ti ti-loader-2 animate-spin" /></div>
          ) : (
            <div className="divide-y divide-[var(--outline-v)] max-h-96 overflow-y-auto">
              {(configs ?? []).map(c => (
                <button
                  key={c.id}
                  onClick={() => selectConfig(c.id)}
                  className={`w-full text-left px-4 py-3 transition-colors ${selectedId === c.id ? "bg-[var(--info-c)]" : "hover:bg-[var(--bg-mid)]"}`}
                >
                  <div className="font-medium text-[13px] text-[var(--on-bg)]">{c.state_name}</div>
                  <div className="text-[10px] text-[var(--outline)] mt-0.5">{c.state_code}</div>
                </button>
              ))}
              {(configs ?? []).length === 0 && (
                <div className="px-4 py-6 text-center text-[var(--outline)] text-xs">No states configured</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Config panel */}
      <div className="flex-1">
        {msg && (
          <div className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium ${msg.startsWith("Failed") || msg.startsWith("A config") ? "bg-[var(--error-c)] text-[var(--error)]" : "bg-[var(--success-c)] text-[var(--success)]"}`}>
            {msg}
          </div>
        )}

        {!selected ? (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] px-6 py-12 text-center text-[var(--outline)]">
            <i className="ti ti-building-bank text-3xl mb-2 block" />
            Select a state to configure statutory deductions (PT, ESI, LWF)
          </div>
        ) : (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--outline-v)]">
              <span className="font-semibold text-[var(--on-bg)]">{selected.state_name} — Statutory Config</span>
              {hasChanges && (
                <button
                  onClick={saveConfig}
                  disabled={saving}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-[var(--info)] text-white rounded-lg hover:bg-[var(--info)] disabled:opacity-50"
                >
                  {saving ? "Saving…" : <><i className="ti ti-device-floppy text-sm" /> Save</>}
                </button>
              )}
            </div>

            <div className="divide-y divide-[var(--outline-v)]">
              {/* Professional Tax */}
              <Section title="Professional Tax (PT)">
                <ToggleRow
                  label="PT Applicable"
                  value={current.pt_applicable ?? false}
                  onChange={v => setField("pt_applicable", v)}
                />

                {current.pt_applicable && (
                  <PtSlabsEditor slabs={currentSlabs} onAdd={addSlab} onRemove={removeSlab} onUpdate={updateSlab} />
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
                        <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1">Frequency</label>
                        <select
                          value={current.lwf_frequency ?? "monthly"}
                          onChange={e => setField("lwf_frequency", e.target.value as StatutoryConfig["lwf_frequency"])}
                          className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
                        >
                          <option value="monthly">Monthly</option>
                          <option value="halfyearly">Half-yearly</option>
                          <option value="annual">Annual</option>
                        </select>
                      </div>
                    </div>
                    <p className="text-[11px] text-[var(--on-variant)] mt-2">
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
        <NewStatutoryConfigModal
          availableStates={availableStates}
          newStateId={newStateId}
          setNewStateId={setNewStateId}
          saving={saving}
          onClose={() => setShowNew(false)}
          onCreate={createConfig}
        />
      )}
    </div>
  );
}
