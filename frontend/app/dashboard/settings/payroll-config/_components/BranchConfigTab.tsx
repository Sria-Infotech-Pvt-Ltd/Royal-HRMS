"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { BranchPayrollConfig, SalaryStructureListItem } from "@/types/payroll";

interface BranchOption { id: string; branch_name: string; branch_code: string; state_name: string; }
interface PagedResponse<T> { results: T[]; count: number; }

const PF_DEFAULTS = { rate: "12", ceiling: "15,000" };

export default function BranchConfigTab() {
  const { data: configs, loading: configLoading, refetch } = useFetch<BranchPayrollConfig[]>(API.payroll.branchConfig);
  const { data: structures } = useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const { data: branchPage, loading: branchLoading } = useFetch<PagedResponse<BranchOption>>(API.branches.list);

  const branches = branchPage?.results ?? [];
  const loading = configLoading || branchLoading;

  const [selectedBranchId, setSelectedBranchId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [draft, setDraft] = useState<Partial<BranchPayrollConfig>>({});

  const configByBranch = new Map((configs ?? []).map(c => [c.branch, c]));
  const selectedBranch = branches.find(b => b.id === selectedBranchId) ?? null;
  const existingConfig = selectedBranchId ? (configByBranch.get(selectedBranchId) ?? null) : null;
  const current: Partial<BranchPayrollConfig> = { ...existingConfig, ...draft };
  const hasChanges = Object.keys(draft).length > 0;

  function set<K extends keyof BranchPayrollConfig>(key: K, value: BranchPayrollConfig[K]) {
    setDraft(prev => ({ ...prev, [key]: value }));
  }

  function selectBranch(branchId: string) {
    setSelectedBranchId(branchId);
    setDraft({});
  }

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 3000);
  }

  async function saveConfig() {
    if (!selectedBranchId) return;
    setSaving(true);
    try {
      if (existingConfig) {
        await clientApi.put(API.payroll.branchConfigDetail(existingConfig.id), draft);
      } else {
        await clientApi.post(API.payroll.branchConfig, { branch: selectedBranchId, ...draft });
      }
      setDraft({});
      refetch();
      flash("Branch config saved.");
    } catch {
      flash("Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function removeConfig() {
    if (!existingConfig) return;
    setSaving(true);
    try {
      await clientApi.delete(API.payroll.branchConfigDetail(existingConfig.id));
      setDraft({});
      refetch();
      flash("Override removed — branch will use system defaults.");
    } catch {
      flash("Failed to remove override.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex gap-4">
      {/* Branch list — shows ALL branches */}
      <div className="w-60 shrink-0">
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
          <div className="px-4 py-3 border-b border-[var(--outline-v)]">
            <span className="font-semibold text-[13px] text-[var(--on-bg)]">All Company Codes</span>
            <div className="text-[11px] text-[var(--outline)] mt-0.5">Select to view or override PF</div>
          </div>
          {loading ? (
            <div className="px-4 py-6 text-center text-[var(--outline)] text-xs"><i className="ti ti-loader-2 animate-spin" /></div>
          ) : (
            <div className="divide-y divide-[var(--outline-v)] max-h-[480px] overflow-y-auto">
              {branches.map(b => {
                const hasOverride = configByBranch.has(b.id);
                return (
                  <button
                    key={b.id}
                    onClick={() => selectBranch(b.id)}
                    className={`w-full text-left px-4 py-3 transition-colors ${selectedBranchId === b.id ? "bg-[var(--info-c)]" : "hover:bg-[var(--bg-mid)]"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-medium text-[13px] text-[var(--on-bg)] truncate">{b.branch_name}</div>
                      {hasOverride
                        ? <span className="shrink-0 text-[10px] font-semibold text-[var(--info)] bg-[var(--info-c)] border border-[var(--info)] px-1.5 py-0.5 rounded">Custom</span>
                        : <span className="shrink-0 text-[10px] font-semibold text-[var(--outline)] bg-[var(--bg-mid)] px-1.5 py-0.5 rounded">Default</span>
                      }
                    </div>
                    <div className="text-[10px] text-[var(--outline)] mt-0.5">{b.state_name}</div>
                  </button>
                );
              })}
              {branches.length === 0 && (
                <div className="px-4 py-6 text-center text-[var(--outline)] text-xs">No Company Codes found</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Config panel */}
      <div className="flex-1">
        {msg && (
          <div className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium ${msg.startsWith("Failed") ? "bg-[var(--error-c)] text-[var(--error)]" : "bg-[var(--success-c)] text-[var(--success)]"}`}>
            {msg}
          </div>
        )}

        {!selectedBranch ? (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] px-6 py-12 text-center text-[var(--outline)]">
            <i className="ti ti-building text-3xl mb-2 block" />
            <div className="text-sm">Select a Company Code to view its PF configuration</div>
            <div className="text-[11px] mt-1">All Company Codes use standard defaults unless overridden</div>
          </div>
        ) : (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--outline-v)]">
              <div>
                <span className="font-semibold text-[var(--on-bg)]">{selectedBranch.branch_name}</span>
                <span className="ml-2 text-[12px] text-[var(--outline)]">{selectedBranch.state_name}</span>
                {!existingConfig && (
                  <span className="ml-2 text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded">
                    Using system defaults
                  </span>
                )}
                {existingConfig && (
                  <span className="ml-2 text-[11px] font-semibold text-[var(--info)] bg-[var(--info-c)] border border-[var(--info)] px-2 py-0.5 rounded">
                    Custom override active
                  </span>
                )}
              </div>
              <div className="flex gap-2">
                {existingConfig && !hasChanges && (
                  <button
                    onClick={removeConfig}
                    disabled={saving}
                    className="px-3 py-1.5 text-[12px] font-medium text-[var(--error)] border border-[var(--error)] rounded-lg hover:bg-[var(--error-c)] disabled:opacity-50"
                  >
                    Remove Override
                  </button>
                )}
                {hasChanges && (
                  <>
                    <button
                      onClick={() => setDraft({})}
                      className="px-3 py-1.5 text-[12px] font-medium text-[var(--on-variant)] border border-[var(--outline-v)] rounded-lg hover:bg-[var(--bg-mid)]"
                    >
                      Discard
                    </button>
                    <button
                      onClick={saveConfig}
                      disabled={saving}
                      className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-[var(--info)] text-white rounded-lg hover:bg-[var(--info)] disabled:opacity-50"
                    >
                      {saving ? "Saving…" : <><i className="ti ti-device-floppy text-sm" /> Save Override</>}
                    </button>
                  </>
                )}
              </div>
            </div>

            <div className="px-5 py-5 space-y-5">
              {/* Defaults notice — shown for all branches */}
              {!existingConfig && (
                <div className="flex items-start gap-3 px-4 py-3 bg-emerald-50 border border-emerald-100 rounded-xl text-[12px] text-emerald-800">
                  <i className="ti ti-info-circle mt-0.5 shrink-0" />
                  <span>
                    This branch uses <strong>system defaults</strong> — PF at {PF_DEFAULTS.rate}% employee / {PF_DEFAULTS.rate}% employer on basic salary up to ₹{PF_DEFAULTS.ceiling}.
                    Override below only if this branch has non-standard PF rules (e.g. PF-exempt establishment).
                  </span>
                </div>
              )}

              {/* Salary structure override */}
              <div>
                <div className="text-[12px] font-bold text-[var(--on-variant)] uppercase tracking-wider mb-3">Salary Structure</div>
                <div>
                  <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1">Structure Override</label>
                  <div className="text-[11px] text-[var(--outline)] mb-2">Leave blank to use the company default structure</div>
                  <select
                    value={current.salary_structure ?? ""}
                    onChange={e => set("salary_structure", e.target.value || null as unknown as string)}
                    className="w-full max-w-xs rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
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
                <div className="text-[12px] font-bold text-[var(--on-variant)] uppercase tracking-wider mb-3">
                  Provident Fund (PF)
                  {!existingConfig && <span className="ml-2 normal-case font-normal text-[var(--outline)]">— defaults shown, edit to override</span>}
                </div>

                <div className="flex items-center justify-between mb-3 py-2 px-3 bg-[var(--bg-mid)] rounded-lg">
                  <div>
                    <span className="text-[13px] font-medium text-[var(--on-bg)]">PF Applicable</span>
                    {!existingConfig && <span className="ml-2 text-[11px] text-[var(--outline)]">(default: yes)</span>}
                  </div>
                  <button
                    onClick={() => set("pf_applicable", !(current.pf_applicable ?? true))}
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${current.pf_applicable ?? true ? "bg-[var(--info)]" : "bg-[var(--bg-mid)]"}`}
                  >
                    <span className={`inline-block h-3.5 w-3.5 rounded-full bg-[var(--surface)] shadow transition-transform ${current.pf_applicable ?? true ? "translate-x-4" : "translate-x-0.5"}`} />
                  </button>
                </div>

                {(current.pf_applicable ?? true) && (
                  <div className="grid grid-cols-3 gap-3">
                    <NumField
                      label="Employee Rate (%)"
                      placeholder="Default: 12"
                      value={String(current.pf_employee_rate ?? "")}
                      onChange={v => set("pf_employee_rate", v)}
                    />
                    <NumField
                      label="Employer Rate (%)"
                      placeholder="Default: 12"
                      value={String(current.pf_employer_rate ?? "")}
                      onChange={v => set("pf_employer_rate", v)}
                    />
                    <NumField
                      label="Wage Ceiling (₹)"
                      placeholder="Default: 15000"
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
    </div>
  );
}

function NumField({ label, placeholder, value, onChange }: {
  label: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1">{label}</label>
      <input
        type="number"
        step="0.01"
        min={0}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
      />
    </div>
  );
}
