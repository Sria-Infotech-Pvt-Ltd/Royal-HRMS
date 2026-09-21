"use client";

import { useRef, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SalaryStructure, SalaryStructureListItem, SalaryComponent } from "@/types/payroll";

const CALC_LABEL: Record<string, string> = {
  percentage_of_ctc:   "% of CTC",
  percentage_of_basic: "% of Basic",
  fixed:               "Fixed ₹",
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
  calculation_type: "percentage_of_ctc" | "percentage_of_basic" | "fixed" | "metro_hra_of_basic";
  value: string;
  is_taxable: boolean;
  order: string;
}

const EMPTY_COMP: ComponentFormState = {
  name: "", component_type: "earning", calculation_type: "percentage_of_ctc",
  value: "", is_taxable: true, order: "0",
};

export default function SalaryStructuresTab() {
  // List endpoint returns items WITHOUT components — only detail has components
  const { data: structures, loading: listLoading, refetch: refetchList } =
    useFetch<SalaryStructureListItem[]>(API.payroll.structures);

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Detail fetch keyed on selectedId — null URL skips the fetch
  const { data: selectedDetail, loading: detailLoading, refetch: refetchDetail } =
    useFetch<SalaryStructure>(selectedId ? API.payroll.structure(selectedId) : null);

  const [showNewStructure, setShowNewStructure] = useState(false);
  const [newStructName,    setNewStructName]    = useState("");
  const [newStructDesc,    setNewStructDesc]    = useState("");
  const [newStructDefault, setNewStructDefault] = useState(false);
  const [showAddComp, setShowAddComp] = useState(false);
  const [compForm, setCompForm] = useState<ComponentFormState>(EMPTY_COMP);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  // Sidebar item (name, default flag) from the list; components from the detail
  const selectedItem = structures?.find(s => s.id === selectedId) ?? null;
  const components   = selectedDetail?.components ?? [];

  function flash(text: string) {
    setMsg(text);
    setTimeout(() => setMsg(null), 3000);
  }

  function selectStructure(id: string) {
    setSelectedId(id);
    setShowAddComp(false);
    setCompForm(EMPTY_COMP);
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
      flash("Failed to create structure.");
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
      flash("Failed to update default.");
    }
  }

  async function addComponent() {
    if (!selectedId || !compForm.name.trim() || !compForm.value) return;
    setSaving(true);
    try {
      await clientApi.post(API.payroll.components(selectedId), {
        name: compForm.name.trim(),
        component_type: compForm.component_type,
        calculation_type: compForm.calculation_type,
        value: compForm.value,
        is_taxable: compForm.is_taxable,
        order: Number(compForm.order),
      });
      setCompForm(EMPTY_COMP);
      setShowAddComp(false);
      refetchDetail();
      flash("Component added.");
    } catch {
      flash("Failed to add component.");
    } finally {
      setSaving(false);
    }
  }

  async function toggleComponent(comp: SalaryComponent) {
    if (!selectedId) return;
    try {
      await clientApi.put(API.payroll.component(selectedId, comp.id), { is_active: !comp.is_active });
      refetchDetail();
    } catch {
      flash("Failed to update component.");
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
          <div className={`mb-3 px-4 py-2.5 rounded-lg text-sm font-medium ${msg.startsWith("Failed") ? "bg-[var(--error-c)] text-[var(--error)]" : "bg-[var(--success-c)] text-[var(--success)]"}`}>
            {msg}
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
                <button
                  onClick={() => setShowAddComp(true)}
                  className="flex items-center gap-1.5 text-[12px] bg-[var(--info)] text-white px-3 py-1.5 rounded-lg hover:bg-[var(--info)] transition-colors"
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
                      {["Component", "Type", "Calc", "Value", "Taxable", "Order", "Status", ""].map(h => (
                        <th key={h} className="text-left text-[11px] font-semibold text-[var(--on-variant)] uppercase tracking-wider px-4 py-3 whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--outline-v)]">
                    {components.map(comp => (
                      <tr key={comp.id} className={`hover:bg-[var(--bg-mid)] transition-colors ${!comp.is_active ? "opacity-50" : ""}`}>
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
                            : `${comp.value}%`}
                        </td>
                        <td className="px-4 py-3 text-[12px] text-[var(--on-variant)]">{comp.is_taxable ? "Yes" : "No"}</td>
                        <td className="px-4 py-3 text-[12px] text-[var(--on-variant)]">{comp.order}</td>
                        <td className="px-4 py-3">
                          <button
                            onClick={() => toggleComponent(comp)}
                            className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${comp.is_active ? "bg-[var(--info)]" : "bg-[var(--bg-mid)]"}`}
                          >
                            <span className={`inline-block h-3.5 w-3.5 rounded-full bg-[var(--surface)] shadow transition-transform ${comp.is_active ? "translate-x-4" : "translate-x-0.5"}`} />
                          </button>
                        </td>
                        <td className="px-4 py-3" />
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
        <Modal title="New Salary Structure" onClose={() => setShowNewStructure(false)}>
          <div className="flex flex-col gap-4">
            <Field label="Name" required>
              <input
                type="text"
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
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
              />
            </Field>
            <div className="flex items-center gap-2 py-1">
              <input
                id="is-default"
                type="checkbox"
                checked={newStructDefault}
                onChange={e => setNewStructDefault(e.target.checked)}
                className="rounded"
              />
              <label htmlFor="is-default" className="text-[13px] text-[var(--on-bg)] cursor-pointer">
                Set as company default structure
              </label>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 mt-4">
            <button onClick={() => setShowNewStructure(false)} className="px-4 py-2 text-sm text-[var(--on-variant)] border border-[var(--outline-v)] rounded-lg hover:bg-[var(--bg-mid)]">Cancel</button>
            <button
              onClick={createStructure}
              disabled={saving || !newStructName.trim()}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-[var(--info)] text-white rounded-lg hover:bg-[var(--info)] disabled:opacity-50"
            >
              {saving ? "Creating…" : "Create Structure"}
            </button>
          </div>
        </Modal>
      )}

      {/* Add component modal */}
      {showAddComp && selectedItem && (
        <Modal title={`Add Component — ${selectedItem.name}`} onClose={() => { setShowAddComp(false); setCompForm(EMPTY_COMP); }}>
          <div className="flex flex-col gap-4">
            <Field label="Component Name" required>
              <input
                type="text"
                placeholder="e.g. Basic, HRA, Special Allowance"
                value={compForm.name}
                onChange={e => setCompForm(p => ({ ...p, name: e.target.value }))}
                className="w-full rounded-lg border border-[var(--outline-v)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--info)]"
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Type">
                <select
                  value={compForm.component_type}
                  onChange={e => setCompForm(p => ({ ...p, component_type: e.target.value as ComponentFormState["component_type"] }))}
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
                  <option value="fixed">Fixed Amount</option>
                  <option value="metro_hra_of_basic">Metro HRA (50%/40% of Basic)</option>
                </select>
              </Field>
            </div>
            {compForm.calculation_type === "metro_hra_of_basic" && (
              <p className="text-[12px] text-[var(--on-variant)] -mt-2 mb-1">
                Computed automatically from each employee&apos;s branch (50% of Basic if the branch is marked Metro, 40% otherwise) — the Percentage field below is ignored for this calculation type.
              </p>
            )}
            <div className="grid grid-cols-2 gap-3">
              <Field label={compForm.calculation_type === "fixed" ? "Amount (₹)" : "Percentage (%)"} required={compForm.calculation_type !== "metro_hra_of_basic"}>
                <input
                  type="number"
                  step="0.01"
                  min={0}
                  value={compForm.value}
                  onChange={e => setCompForm(p => ({ ...p, value: e.target.value }))}
                  disabled={compForm.calculation_type === "metro_hra_of_basic"}
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
            <div className="flex items-center gap-2 py-1">
              <input
                id="is-taxable"
                type="checkbox"
                checked={compForm.is_taxable}
                onChange={e => setCompForm(p => ({ ...p, is_taxable: e.target.checked }))}
                className="rounded"
              />
              <label htmlFor="is-taxable" className="text-[13px] text-[var(--on-bg)] cursor-pointer">Taxable</label>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 mt-4">
            <button onClick={() => { setShowAddComp(false); setCompForm(EMPTY_COMP); }} className="px-4 py-2 text-sm text-[var(--on-variant)] border border-[var(--outline-v)] rounded-lg hover:bg-[var(--bg-mid)]">Cancel</button>
            <button
              onClick={addComponent}
              disabled={saving || !compForm.name.trim() || !compForm.value}
              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold bg-[var(--info)] text-white rounded-lg hover:bg-[var(--info)] disabled:opacity-50"
            >
              {saving ? "Adding…" : "Add Component"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside a field and releasing past the modal's edge would otherwise land
  // on the overlay and close it mid-input. Only close when the gesture both
  // started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="fixed inset-0 z-[1000] bg-black/40 flex items-center justify-center p-4"
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => mouseDownOnOverlay.current && e.target === e.currentTarget && onClose()}
    >
      <div className="bg-[var(--surface)] rounded-2xl w-full max-w-md shadow-2xl">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--outline-v)]">
          <div className="font-semibold text-[var(--on-bg)]">{title}</div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-[var(--outline)] hover:bg-[var(--bg-mid)]"><i className="ti ti-x" /></button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
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
