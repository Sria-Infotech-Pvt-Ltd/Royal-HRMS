"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ConfirmModal from "@/components/ConfirmModal";
import type { CompanyAllowance, PayrollSettings, SalaryStructure, SalaryStructureListItem, SalaryComponent } from "@/types/payroll";

const CALC_LABEL: Record<string, string> = {
  percentage_of_ctc:   "% of CTC",
  percentage_of_basic: "% of Basic",
  percentage_of_basic_plus_da: "% of Basic + DA",
  fixed:               "Fixed ₹",
  balance_to_ctc:      "Balances earnings to CTC",
  metro_hra_of_basic:  "Metro HRA (50%/40% of Basic)",
};

const TYPE_CLS: Record<string, string> = {
  earning:   "bg-[var(--info-c)] text-[var(--info)]",
  deduction: "bg-[var(--error-c)] text-[var(--error)]",
  allowance: "bg-violet-50 text-violet-700",
};

interface ComponentFormState {
  name: string;
  component_type: "earning" | "deduction" | "allowance";
  calculation_type: SalaryComponent["calculation_type"];
  value: string;
  is_taxable: boolean;
  order: string;
}

function nextPayrollCycleStart(startDay: number): string {
  const today = new Date();
  let year = today.getFullYear();
  let month = today.getMonth();
  const dateFor = (targetYear: number, targetMonth: number) =>
    new Date(targetYear, targetMonth, Math.min(startDay, new Date(targetYear, targetMonth + 1, 0).getDate()));
  let start = dateFor(year, month);
  if (start <= new Date(year, month, today.getDate())) {
    month += 1;
    if (month > 11) { year += 1; month = 0; }
    start = dateFor(year, month);
  }
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${start.getFullYear()}-${pad(start.getMonth() + 1)}-${pad(start.getDate())}`;
}

const EMPTY_COMP: ComponentFormState = {
  name: "", component_type: "earning", calculation_type: "percentage_of_ctc",
  value: "", is_taxable: true, order: "0",
};

export default function SalaryStructuresTab() {
  // List endpoint returns items WITHOUT components — only detail has components
  const { data: structures, loading: listLoading, refetch: refetchList } =
    useFetch<SalaryStructureListItem[]>(API.payroll.structures);
  const { data: allowances, refetch: refetchAllowances } =
    useFetch<CompanyAllowance[]>(API.payroll.allowances);
  const { data: payrollSettings } = useFetch<PayrollSettings>(API.payroll.settings);
  const canDelete = usePermission("payroll.delete");

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Detail fetch keyed on selectedId — null URL skips the fetch
  const { data: selectedDetail, loading: detailLoading, refetch: refetchDetail } =
    useFetch<SalaryStructure>(selectedId ? API.payroll.structure(selectedId) : null);

  const [showNewStructure, setShowNewStructure] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [newStructName,    setNewStructName]    = useState("");
  const [newStructDesc,    setNewStructDesc]    = useState("");
  const [newStructDefault, setNewStructDefault] = useState(false);
  const [showAddComp, setShowAddComp] = useState(false);
  const [selectedAllowanceId, setSelectedAllowanceId] = useState("");
  const [compForm, setCompForm] = useState<ComponentFormState>(EMPTY_COMP);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ text: string; isError: boolean } | null>(null);
  const [pendingComponentChange, setPendingComponentChange] = useState<{
    component: SalaryComponent;
    changes: Partial<Pick<SalaryComponent, "is_active" | "order">>;
    orderedIds?: string[];
  } | null>(null);
  const [componentEffectiveDate, setComponentEffectiveDate] = useState("");
  const [changeSaving, setChangeSaving] = useState(false);

  // Sidebar item (name, default flag) from the list; components from the detail
  const selectedItem = structures?.find(s => s.id === selectedId) ?? null;
  const components   = selectedDetail?.components ?? [];
  const activeAllowances = (allowances ?? []).filter(allowance => allowance.is_active);
  const selectedAllowance = activeAllowances.find(allowance => allowance.id === selectedAllowanceId);
  const nextCycleDate = nextPayrollCycleStart(payrollSettings?.cycle_start_day ?? 1);

  function flash(text: string, isError = false) {
    setMsg({ text, isError });
    setTimeout(() => setMsg(null), isError ? 5000 : 3000);
  }

  function selectStructure(id: string) {
    setSelectedId(id);
    setShowAddComp(false);
    setCompForm(EMPTY_COMP);
    setSelectedAllowanceId("");
  }

  async function createStructure() {
    if (!newStructName.trim()) return;
    setSaving(true);
    try {
      await clientApi.post(API.payroll.structures, {
        name: newStructName.trim(),
        description: newStructDesc.trim(),
        is_default: newStructDefault,
      });
      setShowNewStructure(false);
      setNewStructName(""); setNewStructDesc(""); setNewStructDefault(false);
      refetchList();
      flash("Salary structure created.");
    } catch {
      flash("Failed to create structure.", true);
    } finally {
      setSaving(false);
    }
  }

  async function toggleDefault(id: string) {
    try {
      await clientApi.put(API.payroll.structure(id), { is_default: true });
      refetchList();
      refetchDetail();
    } catch {
      flash("Failed to update default.", true);
    }
  }

  async function deleteStructure() {
    if (!selectedItem || selectedItem.is_default) return;
    setSaving(true);
    try {
      await clientApi.delete(API.payroll.structure(selectedItem.id));
      setShowDeleteConfirm(false);
      setSelectedId(null);
      refetchList();
      flash("Salary structure removed from active use. Payroll history is preserved.");
    } catch (err: unknown) {
      // The server says why (for example how many employees still use it).
      setShowDeleteConfirm(false);
      flash((err as { message?: string })?.message || "Could not delete this salary structure. Please try again.", true);
    } finally {
      setSaving(false);
    }
  }

  async function addComponent() {
    const valueRequired = !["metro_hra_of_basic", "balance_to_ctc"].includes(compForm.calculation_type);
    if (!selectedId || !compForm.name.trim() || (valueRequired && !compForm.value)) return;
    if (compForm.component_type === "allowance" && !selectedAllowance) {
      flash("Choose an active allowance from the company catalogue first.", true);
      return;
    }
    const value = Number(compForm.value || "0");
    if (Number.isNaN(value) || value < 0) { flash("Enter a non-negative value.", true); return; }
    if ([
      "percentage_of_ctc",
      "percentage_of_basic",
      "percentage_of_basic_plus_da",
    ].includes(compForm.calculation_type) && value > 100) {
      flash("Percentage cannot exceed 100.", true);
      return;
    }
    setSaving(true);
    try {
      await clientApi.post(API.payroll.components(selectedId), {
        name: compForm.component_type === "allowance" && selectedAllowance
          ? selectedAllowance.name
          : compForm.name.trim(),
        component_type: compForm.component_type,
        calculation_type: compForm.calculation_type,
        value: compForm.value || "0",
        is_taxable: compForm.component_type === "allowance" && selectedAllowance
          ? selectedAllowance.is_taxable
          : compForm.is_taxable,
        order: Number(compForm.order),
        effective_from: componentEffectiveDate || nextCycleDate,
      });
      setCompForm(EMPTY_COMP);
      setShowAddComp(false);
      refetchDetail();
      flash("Component added.");
    } catch {
      flash("Failed to add component.", true);
    } finally {
      setSaving(false);
    }
  }

  async function toggleComponent(comp: SalaryComponent) {
    setPendingComponentChange({ component: comp, changes: { is_active: !comp.is_active } });
    setComponentEffectiveDate(nextCycleDate);
  }

  function scheduleOrderChange(comp: SalaryComponent, offset: number) {
    const ordered = components.slice().sort((left, right) => left.order - right.order);
    const currentIndex = ordered.findIndex(component => component.id === comp.id);
    const targetIndex = currentIndex + offset;
    if (targetIndex < 0 || targetIndex >= ordered.length) return;
    [ordered[currentIndex], ordered[targetIndex]] = [ordered[targetIndex], ordered[currentIndex]];
    setPendingComponentChange({
      component: comp,
      changes: {},
      orderedIds: ordered.map(component => component.id),
    });
    setComponentEffectiveDate(nextCycleDate);
  }

  async function saveComponentChange() {
    if (!selectedId || !pendingComponentChange || !componentEffectiveDate) return;
    setChangeSaving(true);
    try {
      if (pendingComponentChange.orderedIds) {
        await clientApi.post(API.payroll.reorderComponents(selectedId), {
          component_ids: pendingComponentChange.orderedIds,
          effective_from: componentEffectiveDate,
        });
      } else {
        await clientApi.put(
          API.payroll.component(selectedId, pendingComponentChange.component.id),
          { ...pendingComponentChange.changes, effective_from: componentEffectiveDate },
        );
      }
      setPendingComponentChange(null);
      refetchDetail();
      flash(`Component change scheduled for ${componentEffectiveDate}.`);
    } catch {
      flash("Could not schedule this component change.", true);
    } finally {
      setChangeSaving(false);
    }
  }

  return (
    <div className="flex gap-4">
      {/* Structure list */}
      <div className="w-64 shrink-0">
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--outline-v)]">
            <span className="font-semibold text-[13px] text-[var(--on-bg)]">Structures</span>
            <button
              onClick={() => setShowNewStructure(true)}
              className="p-1 rounded-lg text-[var(--info)] hover:bg-[var(--info-c)] transition-colors"
              title="Add structure"
            >
              <i className="ti ti-plus text-sm" />
            </button>
          </div>

          {listLoading ? (
            <div className="px-4 py-6 text-center text-[var(--outline)] text-xs">
              <i className="ti ti-loader-2 animate-spin" /> Loading…
            </div>
          ) : (
            <div className="divide-y divide-[var(--outline-v)]">
              {(structures ?? []).map(s => (
                <button
                  key={s.id}
                  onClick={() => selectStructure(s.id)}
                  className={`w-full text-left px-4 py-3 transition-colors ${selectedId === s.id ? "bg-[var(--info-c)]" : "hover:bg-[var(--bg-mid)]"}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[13px] text-[var(--on-bg)] flex-1 truncate">{s.name}</span>
                    {s.is_default && <span className="text-[10px] bg-[var(--info-c)] text-[var(--info)] px-1.5 py-0.5 rounded font-semibold">Default</span>}
                  </div>
                  {s.description && <div className="text-[11px] text-[var(--outline)] mt-0.5 truncate">{s.description}</div>}
                </button>
              ))}
              {!listLoading && (structures ?? []).length === 0 && (
                <div className="px-4 py-6 text-center text-[var(--outline)] text-xs">No structures yet</div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Components panel */}
      <div className="flex-1">
        {msg && (
          <div className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium ${msg.isError ? "bg-[var(--error-c)] text-[var(--error)]" : "bg-[var(--success-c)] text-[var(--success)]"}`}>
            {msg.text}
          </div>
        )}

        {!selectedItem ? (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] px-6 py-12 text-center text-[var(--outline)]">
            <i className="ti ti-stack text-3xl mb-2 block" />
            Select a structure to view and edit its components
          </div>
        ) : (
          <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--outline-v)]">
              <div>
                <span className="font-semibold text-[var(--on-bg)]">{selectedItem.name}</span>
                {selectedItem.description && <span className="ml-2 text-[12px] text-[var(--outline)]">{selectedItem.description}</span>}
              </div>
              <div className="flex items-center gap-2">
                {!selectedItem.is_default && (
                  <button
                    onClick={() => toggleDefault(selectedItem.id)}
                    className="text-[12px] text-[var(--info)] border border-[var(--info)] hover:bg-[var(--info-c)] px-3 py-1.5 rounded-lg transition-colors"
                  >
                    Set as Default
                  </button>
                )}
                {canDelete && (
                  <button
                    type="button"
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={selectedItem.is_default}
                    title={selectedItem.is_default ? "Set another structure as default before deleting this one." : "Delete this salary structure"}
                    className="btn btn-ghost shrink-0 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <i className="ti ti-trash" /> Delete
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setShowAddComp(true);
                    refetchAllowances();
                    setSelectedAllowanceId("");
                    setCompForm(EMPTY_COMP);
                    setComponentEffectiveDate(nextCycleDate);
                  }}
                  className="btn btn-filled shrink-0"
                >
                  <i className="ti ti-plus text-xs" /> Add Component
                </button>
              </div>
            </div>

            {detailLoading ? (
              <div className="px-4 py-10 text-center text-[var(--outline)] text-xs">
                <i className="ti ti-loader-2 animate-spin text-lg" />
                <div className="mt-2">Loading components…</div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[var(--bg-mid)] border-b border-[var(--outline-v)]">
                      {["Component", "Type", "Calc", "Value", "Taxable", "Effective from", "Order", "Status"].map(h => (
                        <th key={h} className="text-left text-[11px] font-semibold text-[var(--on-variant)] uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--outline-v)]">
                    {components.map(comp => (
                      <tr key={comp.id} className="hover:bg-[var(--bg-mid)] transition-colors">
                        <td className="px-4 py-3 font-semibold text-[var(--on-bg)]">{comp.name}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${TYPE_CLS[comp.component_type] ?? ""}`}>
                            {comp.component_type}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-[var(--on-variant)] text-[12px]">{CALC_LABEL[comp.calculation_type]}</td>
                        <td className="px-4 py-3 font-semibold text-[var(--on-bg)]">
                          {comp.calculation_type === "fixed"
                            ? `₹${Number(comp.value).toLocaleString("en-IN")}`
                            : comp.calculation_type === "metro_hra_of_basic"
                            ? "50% / 40%"
                            : comp.calculation_type === "balance_to_ctc"
                            ? "Remaining CTC"
                            : `${comp.value}%`}
                        </td>
                        <td className="px-4 py-3 text-[12px] text-[var(--on-variant)]">{comp.is_taxable ? "Yes" : "No"}</td>
                        <td className="px-4 py-3 text-[12px] text-[var(--on-variant)]">{comp.effective_from}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              onClick={() => scheduleOrderChange(comp, -1)}
                              disabled={components.slice().sort((left, right) => left.order - right.order)[0]?.id === comp.id}
                              className="rounded p-1 text-[var(--on-variant)] hover:bg-[var(--outline-v)] disabled:opacity-30"
                              aria-label={`Move ${comp.name} up`}
                            >
                              <i className="ti ti-arrow-up" />
                            </button>
                            <span className="text-[12px] text-[var(--on-variant)]">{comp.order}</span>
                            <button
                              type="button"
                              onClick={() => scheduleOrderChange(comp, 1)}
                              disabled={components.slice().sort((left, right) => left.order - right.order)[components.length - 1]?.id === comp.id}
                              className="rounded p-1 text-[var(--on-variant)] hover:bg-[var(--outline-v)] disabled:opacity-30"
                              aria-label={`Move ${comp.name} down`}
                            >
                              <i className="ti ti-arrow-down" />
                            </button>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <button
                            type="button"
                            onClick={() => toggleComponent(comp)}
                            aria-pressed={comp.is_active}
                            aria-label={`${comp.is_active ? "Deactivate" : "Activate"} ${comp.name}`}
                            title={`Click to ${comp.is_active ? "deactivate" : "activate"} ${comp.name}`}
                            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold transition-colors ${
                              comp.is_active
                                ? "bg-[var(--success-c)] text-[var(--success)]"
                                : "bg-[var(--bg-mid)] text-[var(--on-variant)]"
                            }`}
                          >
                            <span className={`h-1.5 w-1.5 rounded-full ${
                              comp.is_active ? "bg-[var(--success)]" : "bg-[var(--outline)]"
                            }`} />
                            {comp.is_active ? "Active" : "Inactive"}
                          </button>
                        </td>
                      </tr>
                    ))}
                    {components.length === 0 && (
                      <tr>
                        <td colSpan={8} className="px-4 py-8 text-center text-[var(--outline)] text-sm">No components yet — click &quot;Add Component&quot; above</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* New structure modal */}
      {showNewStructure && (
        <Modal
          title={<><i className="ti ti-layers" style={{ marginRight: 8, color: "var(--primary)" }} />Create Salary Structure</>}
          onClose={() => setShowNewStructure(false)}
          maxWidth={520}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setShowNewStructure(false)} disabled={saving}>Cancel</button>
              <button className="btn btn-filled" onClick={createStructure} disabled={saving || !newStructName.trim()}>
                {saving ? "Creating…" : "Create Structure"}
              </button>
            </>
          }
        >
          <div className="flex flex-col gap-5">
            <p className="text-sm leading-relaxed -mt-1" style={{ color: "var(--on-variant)" }}>
              Set up a reusable salary template. You can add earnings, allowances, and deductions after creating it.
            </p>
            <Field label="Name" required>
              <input
                type="text"
                autoFocus
                maxLength={100}
                placeholder="e.g. Standard, Management, Executive"
                value={newStructName}
                onChange={e => setNewStructName(e.target.value)}
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
              />
            </Field>
            <Field label="Description">
              <input
                type="text"
                placeholder="Optional description"
                value={newStructDesc}
                onChange={e => setNewStructDesc(e.target.value)}
                maxLength={500}
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
              />
            </Field>
            <label htmlFor="is-default" className="flex items-start gap-3 rounded-xl border border-[var(--outline-v)] p-4 cursor-pointer hover:bg-[var(--bg-mid)] transition-colors">
              <input
                id="is-default"
                type="checkbox"
                checked={newStructDefault}
                onChange={e => setNewStructDefault(e.target.checked)}
                className="mt-0.5 rounded"
              />
              <span>
                <span className="block text-[13px] font-semibold" style={{ color: "var(--on-bg)" }}>Set as company default</span>
                <span className="block text-xs mt-1" style={{ color: "var(--on-variant)" }}>
                  Use this structure as the default when setting up employee compensation.
                </span>
              </span>
            </label>
          </div>
        </Modal>
      )}

      {/* Add component modal */}
      {showAddComp && selectedItem && (
        <Modal
          title={<><i className="ti ti-circle-plus" style={{ marginRight: 8, color: "var(--primary)" }} />Add Component — {selectedItem.name}</>}
          onClose={() => { setShowAddComp(false); setCompForm(EMPTY_COMP); }}
          maxWidth={560}
          footer={
            <>
              <button
                className="btn btn-ghost"
                onClick={() => { setShowAddComp(false); setCompForm(EMPTY_COMP); }}
                disabled={saving}
              >
                Cancel
              </button>
              <button
                className="btn btn-filled"
                onClick={addComponent}
                disabled={saving || !compForm.name.trim() || (
                  !["metro_hra_of_basic", "balance_to_ctc"].includes(compForm.calculation_type) && !compForm.value
                )}
              >
                {saving ? "Adding…" : "Add Component"}
              </button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type">
                <select
                  value={compForm.component_type}
                  onChange={e => {
                    const nextType = e.target.value as ComponentFormState["component_type"];
                    setCompForm(p => ({ ...p, component_type: nextType, name: nextType === "allowance" ? "" : p.name }));
                    setSelectedAllowanceId("");
                  }}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
                >
                  <option value="earning">Earning</option>
                  <option value="allowance">Allowance</option>
                  <option value="deduction">Deduction</option>
                </select>
              </Field>
              <Field label="Calculation">
                <select
                  value={compForm.calculation_type}
                  onChange={e => {
                    const next = e.target.value as ComponentFormState["calculation_type"];
                    setCompForm(p => ({ ...p, calculation_type: next, value: next === "metro_hra_of_basic" ? "0" : p.value }));
                  }}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] field-select"
                >
                  <option value="percentage_of_ctc">% of CTC</option>
                  <option value="percentage_of_basic">% of Basic</option>
                  <option value="percentage_of_basic_plus_da">% of Basic + DA</option>
                  <option value="fixed">Fixed Amount</option>
                  <option value="balance_to_ctc">Balances earnings to CTC</option>
                  <option value="metro_hra_of_basic">Metro HRA (50%/40% of Basic)</option>
                </select>
              </Field>
            </div>
            {compForm.component_type === "allowance" ? (
              <Field label="Company allowance" required>
                <select
                  value={selectedAllowanceId}
                  onChange={event => {
                    const allowance = activeAllowances.find(item => item.id === event.target.value);
                    setSelectedAllowanceId(event.target.value);
                    setCompForm(previous => ({
                      ...previous,
                      name: allowance?.name ?? "",
                      is_taxable: allowance?.is_taxable ?? true,
                    }));
                  }}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm field-select"
                >
                  <option value="">Select an active allowance</option>
                  {activeAllowances.map(allowance => (
                    <option key={allowance.id} value={allowance.id}>{allowance.name}</option>
                  ))}
                </select>
                {activeAllowances.length === 0 && (
                  <p className="text-[11px] text-[var(--on-variant)] mt-1">
                    Add or activate allowance options in Payroll Settings → Allowances first.
                  </p>
                )}
              </Field>
            ) : (
              <Field label="Component Name" required>
                <input
                  type="text"
                  placeholder="e.g. Basic, HRA, Special Allowance"
                  value={compForm.name}
                  onChange={e => setCompForm(p => ({ ...p, name: e.target.value }))}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
                />
              </Field>
            )}
            {compForm.calculation_type === "metro_hra_of_basic" && (
              <p className="text-[12px] text-[var(--on-variant)] -mt-2 mb-1">
                Computed automatically from each employee&apos;s branch (50% of Basic if the branch is marked Metro, 40% otherwise) — the Percentage field below is ignored for this calculation type.
              </p>
            )}
            {compForm.calculation_type === "balance_to_ctc" && (
              <p className="text-[12px] text-[var(--on-variant)] -mt-2 mb-1">
                The remaining CTC after other enabled earnings and statutory employer contributions.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field
                label={compForm.calculation_type === "fixed" ? "Amount (₹)" : "Percentage (%)"}
                required={!["metro_hra_of_basic", "balance_to_ctc"].includes(compForm.calculation_type)}
              >
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  value={compForm.value}
                  onChange={e => setCompForm(p => ({ ...p, value: e.target.value }))}
                  disabled={["metro_hra_of_basic", "balance_to_ctc"].includes(compForm.calculation_type)}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)] disabled:bg-[var(--bg-mid)] disabled:text-[var(--outline)]"
                />
              </Field>
              <Field label="Display Order">
                <input
                  type="number"
                  min={0}
                  value={compForm.order}
                  onChange={e => setCompForm(p => ({ ...p, order: e.target.value }))}
                  className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
                />
              </Field>
            </div>
            <Field label="Effective from">
              <input
                type="date"
                min={nextCycleDate}
                value={componentEffectiveDate || nextCycleDate}
                onChange={event => setComponentEffectiveDate(event.target.value)}
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm"
              />
              <span className="text-[11px] text-[var(--on-variant)]">
                Defaults to the next payroll cycle; issued payslips are not recalculated.
              </span>
            </Field>
            <div className="flex items-center gap-2 py-1">
              <input
                id="is-taxable"
                type="checkbox"
                checked={compForm.is_taxable}
                onChange={e => setCompForm(p => ({ ...p, is_taxable: e.target.checked }))}
                disabled={compForm.component_type === "allowance" && Boolean(selectedAllowance)}
                className="rounded"
              />
              <label htmlFor="is-taxable" className="text-[13px] text-[var(--on-bg)] cursor-pointer">Taxable</label>
            </div>
          </div>
        </Modal>
      )}
      {pendingComponentChange && (
        <Modal
          title={pendingComponentChange.orderedIds ? "Schedule component order" : "Schedule component change"}
          onClose={() => setPendingComponentChange(null)}
          maxWidth={520}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setPendingComponentChange(null)} disabled={changeSaving}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={saveComponentChange}
                disabled={changeSaving || !componentEffectiveDate || componentEffectiveDate < nextCycleDate}
              >
                {changeSaving ? "Scheduling…" : "Schedule change"}
              </button>
            </>
          }
        >
          <div className="flex flex-col gap-4">
            <p className="text-sm leading-relaxed text-[var(--on-variant)]">
              {pendingComponentChange.orderedIds
                ? `The new component order will apply to ${pendingComponentChange.component.affected_employee_count} affected employee(s).`
                : pendingComponentChange.changes.is_active === false
                ? `Disabling ${pendingComponentChange.component.name} affects ${pendingComponentChange.component.affected_employee_count} employee(s). Existing values and historical payslips are retained; the component will be excluded from future calculations from the selected date.`
                : `Enabling ${pendingComponentChange.component.name} affects ${pendingComponentChange.component.affected_employee_count} employee(s). Previously stored overrides will not be reused; a fresh value must be entered where required.`}
            </p>
            <Field label="Effective from">
              <input
                type="date"
                min={nextCycleDate}
                value={componentEffectiveDate}
                onChange={event => setComponentEffectiveDate(event.target.value)}
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm"
              />
              <span className="text-[11px] text-[var(--on-variant)]">
                Default: next payroll cycle start ({nextCycleDate}).
              </span>
            </Field>
          </div>
        </Modal>
      )}
      {showDeleteConfirm && selectedItem && (
        <ConfirmModal
          title="Deactivate Salary Structure?"
          body={`"${selectedItem.name}" will be removed from the active salary structure list. Existing employee compensation records and payslip history will be preserved.`}
          confirmLabel={saving ? "Deleting…" : "Yes, Delete"}
          danger
          saving={saving}
          onConfirm={deleteStructure}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  );
}

function Field({ label, children, required }: { label: string; children: React.ReactNode; required?: boolean }) {
  return (
    <div>
      <label className="block text-[12px] font-semibold text-[var(--on-bg)] mb-1.5">
        {label}{required && <span className="text-[var(--error)] ml-0.5">*</span>}
      </label>
      {children}
    </div>
  );
}
