"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { BranchPayrollConfig, SalaryStructureListItem } from "@/types/payroll";

interface BranchOption { id: string; branch_name: string; branch_code: string; state: { name: string }; }

export default function BranchConfigTab() {
  const { data: configs, loading, refetch } = useFetch<BranchPayrollConfig[]>(API.payroll.branchConfig);
  const { data: structures } = useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const { data: branches } = useFetch<BranchOption[]>(API.branches.list);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [showNew, setShowNew] = useState(false);
  const [newBranchId, setNewBranchId] = useState("");
  const [draft, setDraft] = useState<Partial<BranchPayrollConfig>>({});

  const selected = configs?.find(c => c.id === selectedId) ?? null;
  const current: Partial<BranchPayrollConfig> = { ...selected, ...draft };

  function set<K extends keyof BranchPayrollConfig>(key: K, value: BranchPayrollConfig[K]) {
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

  async function saveConfig() {
    if (!selectedId) return;
    setSaving(true);
    try {
      await clientApi.put(API.payroll.branchConfigDetail(selectedId), draft);
      setDraft({});
      refetch();
      flash("Branch config saved.");
    } catch {
      flash("Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function createConfig() {
    if (!newBranchId) return;
    setSaving(true);
    try {
      const res = await clientApi.post<{ data: BranchPayrollConfig }>(API.payroll.branchConfig, { branch: newBranchId });
      setShowNew(false);
      setNewBranchId("");
      refetch();
      setSelectedId(res.data.data.id);
      flash("Config created.");
    } catch {
      flash("A config for this branch may already exist.");
    } finally {
      setSaving(false);
    }
  }

  const configuredBranchIds = new Set((configs ?? []).map(c => c.branch));
  const availableBranches = (branches ?? []).filter((b: BranchOption) => !configuredBranchIds.has(b.id));
  const hasChanges = Object.keys(draft).length > 0;

  return (
    <div className="flex gap-4">
      {/* Branch list */}
      <div className="w-56 shrink-0">
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="font-semibold text-[13px] text-gray-900">Branches</span>
            {availableBranches.length > 0 && (
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
                  <div className="font-medium text-[13px] text-gray-900">{c.branch_name}</div>
                  <div className="text-[10px] text-gray-400 mt-0.5">{c.branch_state}</div>
                </button>
              ))}
              {(configs ?? []).length === 0 && (
                <div className="px-4 py-6 text-center text-gray-400 text-xs">No branches configured</div>
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
            <i className="ti ti-building text-3xl mb-2 block" />
            Select a branch to configure its PF rates and salary structure
          </div>
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <div>
                <span className="font-semibold text-gray-900">{selected.branch_name}</span>
                <span className="ml-2 text-[12px] text-gray-400">{selected.branch_state}</span>
              </div>
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

            <div className="px-5 py-5 space-y-5">
              {/* Salary structure override */}
              <div>
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-3">Salary Structure</div>
                <div>
                  <label className="block text-[12px] font-semibold text-gray-700 mb-1">Structure Override</label>
                  <div className="text-[11px] text-gray-400 mb-2">Leave blank to use the company default structure</div>
                  <select
                    value={current.salary_structure ?? ""}
                    onChange={e => set("salary_structure", e.target.value || null as unknown as string)}
                    className="w-full max-w-xs rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
                  >
                    <option value="">— Use company default —</option>
                    {(structures ?? []).filter(s => s.is_active).map(s => (
                      <option key={s.id} value={s.id}>{s.name}{s.is_default ? " (Default)" : ""}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* PF config */}
              <div>
                <div className="text-[12px] font-bold text-gray-500 uppercase tracking-wider mb-3">Provident Fund (PF)</div>
                <div className="flex items-center justify-between mb-3 py-2 px-3 bg-gray-50 rounded-lg">
                  <span className="text-[13px] font-medium text-gray-800">PF Applicable</span>
                  <button
                    onClick={() => set("pf_applicable", !(current.pf_applicable ?? true))}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${current.pf_applicable ?? true ? "bg-blue-800" : "bg-gray-200"}`}
                  >
                    <span className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${current.pf_applicable ?? true ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                </div>
                {(current.pf_applicable ?? true) && (
                  <div className="grid grid-cols-3 gap-3">
                    <NumField
                      label="Employee Rate (%)"
                      value={String(current.pf_employee_rate ?? "")}
                      onChange={v => set("pf_employee_rate", v)}
                    />
                    <NumField
                      label="Employer Rate (%)"
                      value={String(current.pf_employer_rate ?? "")}
                      onChange={v => set("pf_employer_rate", v)}
                    />
                    <NumField
                      label="Wage Ceiling (₹)"
                      value={String(current.pf_wage_ceiling ?? "")}
                      onChange={v => set("pf_wage_ceiling", v)}
                    />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* New branch modal */}
      {showNew && (
        <div className="fixed inset-0 z-[1000] bg-black/40 flex items-center justify-center p-4" onClick={e => e.target === e.currentTarget && setShowNew(false)}>
          <div className="bg-white rounded-2xl w-full max-w-sm shadow-2xl">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="font-semibold text-gray-900">Add Branch Config</div>
              <button onClick={() => setShowNew(false)} className="p-1.5 rounded-lg text-gray-400 hover:bg-gray-100"><i className="ti ti-x" /></button>
            </div>
            <div className="px-6 py-5">
              <label className="block text-[12px] font-semibold text-gray-700 mb-1.5">Branch</label>
              <select
                value={newBranchId}
                onChange={e => setNewBranchId(e.target.value)}
                className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
              >
                <option value="">Select a branch</option>
                {availableBranches.map((b: BranchOption) => (
                  <option key={b.id} value={b.id}>{b.branch_name} — {b.state?.name}</option>
                ))}
              </select>
              <div className="flex items-center justify-end gap-2 mt-4">
                <button onClick={() => setShowNew(false)} className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-100">Cancel</button>
                <button
                  onClick={createConfig}
                  disabled={saving || !newBranchId}
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

function NumField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-gray-700 mb-1">{label}</label>
      <input
        type="number"
        step="0.01"
        min={0}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
      />
    </div>
  );
}
