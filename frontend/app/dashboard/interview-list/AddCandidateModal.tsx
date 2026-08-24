"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import {
  NAME_RE, POSITION_RE, PHONE_RE,
  sanitizeName, sanitizePosition, sanitizePhone, todayDateString,
} from "@/lib/candidateValidation";
import { Branch, Candidate, InterviewMode, RECRUITMENT_API } from "./_data";
import Modal from "@/components/Modal";

interface Props {
  onClose: () => void;
  onSaved: (c: Candidate) => void;
}

interface PickerEmployee { uuid: string; id: string; full_name: string }

const todayStr = todayDateString();

export function AddCandidateModal({ onClose, onSaved }: Props) {
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);

  const [form, setForm] = useState<{
    name: string; email: string; phone: string; position_applied: string;
    branch: string; interview_date: string; interview_time: string;
    interview_mode: InterviewMode; meeting_link: string; interviewer: string; notes: string;
  }>({
    name: "", email: "", phone: "", position_applied: "",
    branch: "", interview_date: "", interview_time: "",
    interview_mode: "in_person", meeting_link: "", interviewer: "", notes: "",
  });
  const [branches,  setBranches]  = useState<Branch[]>([]);
  const [employees, setEmployees] = useState<PickerEmployee[]>([]);
  const [saving,    setSaving]    = useState(false);
  const [error,     setError]     = useState("");

  // Fetch active branches for the dropdown using branch app URL
  useEffect(() => {
    clientApi
      .get<{ data: { results: Branch[] } }>(API.branches.list, {
        params: { status: "active", page_size: 100 },
      })
      .then(r => setBranches(r.data?.data?.results ?? []))
      .catch(() => {/* non-blocking — user can still submit without branch */});
  }, []);

  // Employees for the Interviewer picker — the candidate serializer's
  // `interviewer` field is a straight FK, so it needs the real user uuid,
  // not the human-readable employee_id code `_employee_dict` puts under `id`.
  useEffect(() => {
    clientApi
      .get<{ data: { results: PickerEmployee[] } }>(API.employees.list, { params: { page_size: 200 } })
      .then(r => setEmployees(r.data?.data?.results ?? []))
      .catch(() => {/* non-blocking — user can still submit without an interviewer */});
  }, []);

  // Branch-restricted users (everyone except system_admin) always add candidates
  // to their own branch — lock the field instead of offering every branch.
  const myBranch = branches.find(b => b.branch_name === effectiveBranch);
  useEffect(() => {
    if (!unrestricted && myBranch) {
      setForm(f => (f.branch ? f : { ...f, branch: String(myBranch.id) }));
    }
  }, [unrestricted, myBranch]);

  function set(key: string, val: string) {
    setForm(f => ({ ...f, [key]: val }));
  }

  async function handleSave() {
    const name = form.name.trim();
    const positionApplied = form.position_applied.trim();
    if (!name || !form.email.trim() || !positionApplied) {
      setError("Name, email and position are required.");
      return;
    }
    if (!NAME_RE.test(name)) {
      setError("Full name can only contain letters, spaces, apostrophes, hyphens, and periods — no numbers or special characters.");
      return;
    }
    if (!POSITION_RE.test(positionApplied)) {
      setError("Position applied can only contain letters, spaces, and & / . - — no numbers or other special characters.");
      return;
    }
    if (form.phone.trim() && !PHONE_RE.test(form.phone.trim())) {
      setError("Enter a valid phone number (10 to 15 digits, optionally starting with +).");
      return;
    }
    if (form.interview_date && form.interview_date < todayStr) {
      setError("Interview date cannot be in the past.");
      return;
    }
    // Only unrestricted users actually pick a branch here — everyone else's
    // field is locked/read-only and the backend resolves their branch itself
    // (CandidateListCreateView.post), so this required-check would otherwise
    // block a legitimate submission whenever the best-effort name-match below
    // hasn't resolved form.branch yet (branches list still loading, etc.).
    if (unrestricted && !form.branch) {
      setError("Please select a branch.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await RECRUITMENT_API.create({
        ...form,
        branch: Number(form.branch),
        interviewer: form.interviewer || null,
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
    <Modal
      title="Add Candidate to Interview List"
      onClose={onClose}
      maxWidth={560}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <><i className="ti ti-check" /> Add to List</>}
          </button>
        </>
      }
    >
          {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Full Name *</label>
              <input className="field-input" placeholder="e.g. Anjali Sharma" value={form.name} onChange={e => set("name", sanitizeName(e.target.value))} />
            </div>
            <div className="field-group">
              <label className="field-label">Email Address *</label>
              <input className="field-input" type="email" placeholder="anjali@gmail.com" value={form.email} onChange={e => set("email", e.target.value)} />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Position Applied *</label>
              <input className="field-input" placeholder="e.g. Backend Engineer" value={form.position_applied} onChange={e => set("position_applied", sanitizePosition(e.target.value))} />
            </div>
            <div className="field-group">
              <label className="field-label">Phone</label>
              <input className="field-input" placeholder="+91 98765 43210" value={form.phone} onChange={e => set("phone", sanitizePhone(e.target.value))} />
            </div>
          </div>

          {/* Branch selection — required. Branch-restricted users are locked to their own branch. */}
          <div className="field-group mb-16">
            <label className="field-label">Branch *</label>
            {unrestricted ? (
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
            ) : (
              <input className="field-input" value={effectiveBranch} disabled readOnly />
            )}
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Interview Date</label>
              <input className="field-input" type="date" min={todayStr} value={form.interview_date} onChange={e => set("interview_date", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Interview Time</label>
              <input className="field-input" type="time" value={form.interview_time} onChange={e => set("interview_time", e.target.value)} />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Interview Mode</label>
              <select className="field-input field-select" value={form.interview_mode} onChange={e => set("interview_mode", e.target.value)}>
                <option value="in_person">In-Person</option>
                <option value="video_call">Video Call</option>
                <option value="phone">Phone</option>
              </select>
            </div>
            {form.interview_mode === "video_call" && (
              <div className="field-group">
                <label className="field-label">Meeting Link</label>
                <input className="field-input" type="url" placeholder="https://meet.google.com/..." value={form.meeting_link} onChange={e => set("meeting_link", e.target.value)} />
              </div>
            )}
          </div>

          <div className="field-group mb-16">
            <label className="field-label">Interviewer</label>
            <select className="field-input field-select" value={form.interviewer} onChange={e => set("interviewer", e.target.value)}>
              <option value="">— Select interviewer —</option>
              {employees.map(e => (
                <option key={e.uuid} value={e.uuid}>{e.full_name} ({e.id})</option>
              ))}
            </select>
          </div>

          <div className="field-group">
            <label className="field-label">Notes</label>
            <textarea className="field-input" rows={3} placeholder="Any notes about this candidate..." value={form.notes} onChange={e => set("notes", e.target.value)} />
          </div>
    </Modal>
  );
}
