"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { Branch, Candidate, InterviewMode, RECRUITMENT_API } from "./_data";

interface Props {
  onClose: () => void;
  onSaved: (c: Candidate) => void;
}

export function AddCandidateModal({ onClose, onSaved }: Props) {
  const [form, setForm] = useState<{
    name: string; email: string; phone: string; position_applied: string;
    branch: string; interview_date: string; interview_mode: InterviewMode; notes: string;
  }>({
    name: "", email: "", phone: "", position_applied: "",
    branch: "", interview_date: "", interview_mode: "in_person", notes: "",
  });
  const [branches, setBranches] = useState<Branch[]>([]);
  const [saving,   setSaving]   = useState(false);
  const [error,    setError]    = useState("");

  // Fetch active branches for the dropdown using branch app URL
  useEffect(() => {
    clientApi
      .get<{ data: { results: Branch[] } }>(API.branches.list, {
        params: { status: "active", page_size: 100 },
      })
      .then(r => setBranches(r.data?.data?.results ?? []))
      .catch(() => {/* non-blocking — user can still submit without branch */});
  }, []);

  function set(key: string, val: string) {
    setForm(f => ({ ...f, [key]: val }));
  }

  async function handleSave() {
    if (!form.name.trim() || !form.email.trim() || !form.position_applied.trim()) {
      setError("Name, email and position are required.");
      return;
    }
    if (!form.branch) {
      setError("Please select a branch.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await RECRUITMENT_API.create({
        ...form,
        branch: Number(form.branch),
      });
      onSaved(res.data.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg || "Failed to add candidate.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 560 }}>
        <div className="modal-header">
          <div className="modal-title">Add Candidate to Interview List</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>
        <div className="modal-body">
          {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Full Name *</label>
              <input className="field-input" placeholder="e.g. Anjali Sharma" value={form.name} onChange={e => set("name", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Email Address *</label>
              <input className="field-input" type="email" placeholder="anjali@gmail.com" value={form.email} onChange={e => set("email", e.target.value)} />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Position Applied *</label>
              <input className="field-input" placeholder="e.g. Backend Engineer" value={form.position_applied} onChange={e => set("position_applied", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Phone</label>
              <input className="field-input" placeholder="+91 98765 43210" value={form.phone} onChange={e => set("phone", e.target.value)} />
            </div>
          </div>

          {/* Branch selection — required */}
          <div className="field-group mb-16">
            <label className="field-label">Branch *</label>
            <select
              className="field-input field-select"
              value={form.branch}
              onChange={e => set("branch", e.target.value)}
            >
              <option value="">— Select branch —</option>
              {branches.map(b => (
                <option key={b.id} value={b.id}>
                  {b.branch_name} ({b.branch_code})
                </option>
              ))}
            </select>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Interview Date</label>
              <input className="field-input" type="date" value={form.interview_date} onChange={e => set("interview_date", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Interview Mode</label>
              <select className="field-input field-select" value={form.interview_mode} onChange={e => set("interview_mode", e.target.value)}>
                <option value="in_person">In-Person</option>
                <option value="video_call">Video Call</option>
                <option value="phone">Phone</option>
              </select>
            </div>
          </div>

          <div className="field-group">
            <label className="field-label">Notes</label>
            <textarea className="field-input" rows={3} placeholder="Any notes about this candidate..." value={form.notes} onChange={e => set("notes", e.target.value)} />
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-check" /> Add to List</>}
          </button>
        </div>
      </div>
    </div>
  );
}
