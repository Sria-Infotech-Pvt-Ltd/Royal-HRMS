"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { Holiday, HolidayFormPayload, HolidayType } from "@/types/holidays";

interface BranchOption { id: number; branch_name: string }

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

const INPUT     = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white outline-none transition focus:border-blue-600 focus:ring-2 focus:ring-blue-100";
const INPUT_ERR = "w-full border border-red-400 rounded-lg px-3 py-2 text-sm bg-red-50 outline-none";

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
    if (!form.name.trim()) e.name = "Holiday name is required.";
    if (!form.date)        e.date = "Date is required.";
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <span className="text-sm font-bold text-gray-800">
            {mode === "add" ? "Add Holiday" : `Edit: ${editing?.name}`}
          </span>
          <button onClick={onClose} className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 transition-colors">
            <i className="ti ti-x text-sm" />
          </button>
        </div>
        <div className="px-6 py-5 flex flex-col gap-4">
          {saveErr && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2 flex items-center gap-1.5">
              <i className="ti ti-alert-circle" /> {saveErr}
            </div>
          )}
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5">Holiday Name *</label>
            <input className={errors.name ? INPUT_ERR : INPUT} value={form.name}
              onChange={e => setField("name", e.target.value)} placeholder="e.g. Independence Day" autoFocus maxLength={80} />
            {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Date *</label>
              <input className={errors.date ? INPUT_ERR : INPUT} type="date" value={form.date}
                onChange={e => setField("date", e.target.value)} />
              {errors.date && <p className="text-xs text-red-500 mt-1">{errors.date}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-gray-600 mb-1.5">Type</label>
              <select className={INPUT} value={form.holiday_type} onChange={e => setField("holiday_type", e.target.value as HolidayType)}>
                <option value="national">National</option>
                <option value="regional">Regional</option>
                <option value="company">Company</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5">Applicable Branch</label>
            <select className={INPUT} value={form.branch === null ? "" : String(form.branch)}
              onChange={e => setField("branch", e.target.value === "" ? null : Number(e.target.value))}>
              <option value="">All Branches</option>
              {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 mb-1.5">Description</label>
            <textarea className={INPUT} rows={2} value={form.description}
              onChange={e => setField("description", e.target.value)} placeholder="Optional notes" />
          </div>
          <div className="flex items-center gap-6">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.is_optional} onChange={e => setField("is_optional", e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600" />
              <span className="text-sm text-gray-700">Optional holiday</span>
            </label>
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={form.is_active} onChange={e => setField("is_active", e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600" />
              <span className="text-sm text-gray-700">Active</span>
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-6 pb-5">
          <button onClick={onClose} className="px-4 py-2 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors">
            Cancel
          </button>
          <button onClick={save} disabled={saving}
            className="px-5 py-2 rounded-xl text-sm font-semibold text-white transition-colors flex items-center gap-2"
            style={{ background: saving ? "#7fa3c8" : "#1e4e8c" }}>
            {saving ? <><i className="ti ti-loader-2 animate-spin" /> Saving…</> : mode === "add" ? "Add Holiday" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
