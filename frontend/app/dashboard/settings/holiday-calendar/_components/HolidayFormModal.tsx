"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { Holiday, HolidayFormPayload, HolidayType } from "@/types/holidays";

interface BranchOption { id: number; branch_name: string }

// Mirrors _HOLIDAY_NAME_RE enforced server-side in backend/apps/hrms/serializers.py
// (HolidayCreateSerializer.validate_name) — letters, spaces, apostrophes, periods,
// hyphens, and at least one letter (rejects "12345" or "@#$%^&*").
const HOLIDAY_NAME_RE = /^(?=.*[A-Za-z])[A-Za-z .'-]+$/;

function sanitizeHolidayName(value: string): string {
  return value.replace(/[^A-Za-z .'-]/g, "");
}

interface Props {
  mode:     "add" | "edit";
  editing:  Holiday | null;
  branches: BranchOption[];
  onClose:  () => void;
  onSaved:  () => void;
}

const BLANK: HolidayFormPayload = {
  name: "", date: "", holiday_type: "national", is_optional: false,
  description: "", branch: null, is_active: true,
};

function toForm(h: Holiday): HolidayFormPayload {
  return {
    name: h.name, date: h.date, holiday_type: h.holiday_type, is_optional: h.is_optional,
    description: h.description, branch: h.branch, is_active: h.is_active,
  };
}

const INPUT     = "w-full border border-[var(--outline-v)] rounded-lg px-3 py-2 text-sm text-[var(--on-bg)] bg-[var(--surface)] outline-none transition focus:border-[var(--info)] focus:ring-2 focus:ring-[var(--info)]";
const INPUT_ERR = "w-full border border-[var(--error)] rounded-lg px-3 py-2 text-sm bg-[var(--error-c)] outline-none";

export default function HolidayFormModal({ mode, editing, branches, onClose, onSaved }: Props) {
  const { showToast } = useToast();
  const [form, setForm]       = useState<HolidayFormPayload>(editing ? toForm(editing) : BLANK);
  const [errors, setErrors]   = useState<Record<string, string>>({});
  const [saveErr, setSaveErr] = useState("");
  const [saving, setSaving]   = useState(false);

  function setField<K extends keyof HolidayFormPayload>(key: K, value: HolidayFormPayload[K]) {
    setErrors(prev => { const n = { ...prev }; delete n[key]; return n; });
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function validate() {
    const e: Record<string, string> = {};
    const name = form.name.trim();
    if (!name) e.name = "Holiday name is required.";
    else if (!HOLIDAY_NAME_RE.test(name)) e.name = "Holiday name can only contain letters, spaces, apostrophes, periods, and hyphens — not just numbers or symbols.";
    if (!form.date) e.date = "Date is required.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function save() {
    if (!validate()) return;
    setSaving(true);
    setSaveErr("");
    try {
      const res = mode === "add"
        ? await clientApi.post<{ message: string }>(API.leave.holidays, form)
        : await clientApi.patch<{ message: string }>(API.leave.holidayDetail(editing!.id), form);
      showToast(res.data.message, "success");
      onSaved();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to save holiday.";
      setSaveErr(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-[var(--surface)] rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--outline-v)]">
          <span className="text-sm font-bold text-[var(--on-bg)]">
            {mode === "add" ? "Add Holiday" : `Edit: ${editing?.name}`}
          </span>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--bg-mid)] text-[var(--outline)] transition-colors">
            <i className="ti ti-x text-sm" />
          </button>
        </div>
        <div className="px-6 py-5 flex flex-col gap-4">
          {saveErr && (
            <div className="text-xs text-[var(--error)] bg-[var(--error-c)] border border-[var(--error)] rounded-lg px-3 py-2 flex items-center gap-1.5">
              <i className="ti ti-alert-circle" /> {saveErr}
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5">Holiday Name *</label>
            <input className={errors.name ? INPUT_ERR : INPUT} value={form.name}
              onChange={e => setField("name", sanitizeHolidayName(e.target.value))} placeholder="e.g. Independence Day" autoFocus maxLength={80} />
            {errors.name && <p className="text-xs text-[var(--error)] mt-1">{errors.name}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5">Date *</label>
              <input className={errors.date ? INPUT_ERR : INPUT} type="date" value={form.date}
                onChange={e => setField("date", e.target.value)} />
              {errors.date && <p className="text-xs text-[var(--error)] mt-1">{errors.date}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5">Type</label>
              <select className={`${INPUT} field-select`} value={form.holiday_type} onChange={e => setField("holiday_type", e.target.value as HolidayType)}>
                <option value="national">National</option>
                <option value="regional">Regional</option>
                <option value="company">Company</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5">Applicable Company Code</label>
            <select className={`${INPUT} field-select`} value={form.branch === null ? "" : String(form.branch)}
              onChange={e => setField("branch", e.target.value === "" ? null : Number(e.target.value))}>
              <option value="">All Company Codes</option>
              {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5">Description</label>
            <textarea className={INPUT} rows={2} value={form.description}
              onChange={e => setField("description", e.target.value)} placeholder="Optional notes" />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.is_optional} onChange={e => setField("is_optional", e.target.checked)}
                className="w-4 h-4 rounded border-[var(--outline-v)] text-[var(--info)]" />
              <span className="text-sm text-[var(--on-bg)]">Optional holiday</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.is_active} onChange={e => setField("is_active", e.target.checked)}
                className="w-4 h-4 rounded border-[var(--outline-v)] text-[var(--info)]" />
              <span className="text-sm text-[var(--on-bg)]">Active</span>
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 pb-5">
          <button onClick={onClose} className="px-4 py-2 rounded-xl border border-[var(--outline-v)] text-sm font-medium text-[var(--on-variant)] hover:bg-[var(--bg-mid)] transition-colors">
            Cancel
          </button>
          <button onClick={save} disabled={saving}
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white transition-colors flex items-center gap-2"
            style={{ background: "var(--primary)", opacity: saving ? 0.7 : 1 }}>
            {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : mode === "add" ? "Add Holiday" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
