"use client";

// Company Contact Matrix — who to contact for attendance, WFH, leave and other
// HR matters, and who to escalate to. Visible to every signed-in employee
// (company-wide contacts plus their own branch's); HR with documents.create
// maintains it. Contact details are entered by HR — nothing is pre-filled.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import Modal from "@/components/Modal";
import {
  EMPTY_CONTACT, contactFormError, groupByLevel, levelLabel,
  type CompanyContact, type ContactForm,
} from "@/lib/contactMatrix";

interface ContactsResponse { contacts: CompanyContact[]; can_manage: boolean }
interface BranchOption { id: number; branch_name: string }

export default function ContactMatrixPage() {
  const { data, loading, error, refetch } = useFetch<ContactsResponse>(API.companyPolicy.contacts);
  const canManage = !!data?.can_manage;
  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    canManage ? `${API.branches.list}?page_size=100` : null,
  );
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  const [editing, setEditing]   = useState<{ id: number | null; form: ContactForm } | null>(null);
  const [saving, setSaving]     = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const groups = groupByLevel(data?.contacts ?? []);

  function openNew() { setFormError(null); setEditing({ id: null, form: { ...EMPTY_CONTACT } }); }
  function openEdit(c: CompanyContact) {
    setFormError(null);
    setEditing({
      id: c.id,
      form: {
        name: c.name, designation: c.designation, department: c.department, email: c.email, phone: c.phone,
        purpose: c.purpose, escalation_level: c.escalation_level, branch: c.branch, display_order: c.display_order,
      },
    });
  }

  async function save() {
    if (!editing) return;
    const problem = contactFormError(editing.form);
    if (problem) { setFormError(problem); return; }
    setSaving(true); setFormError(null);
    try {
      if (editing.id === null) await clientApi.post(API.companyPolicy.contacts, editing.form);
      else await clientApi.patch(API.companyPolicy.contactDetail(editing.id), editing.form);
      setEditing(null);
      refetch();
    } catch (err: unknown) {
      setFormError((err as { message?: string })?.message ?? "Could not save the contact.");
    } finally { setSaving(false); }
  }

  async function remove(c: CompanyContact) {
    if (!window.confirm(`Remove ${c.name} from the Contact Matrix?`)) return;
    try {
      await clientApi.delete(API.companyPolicy.contactDetail(c.id));
      refetch();
    } catch (err: unknown) {
      window.alert((err as { message?: string })?.message ?? "Could not remove the contact.");
    }
  }

  const set = <K extends keyof ContactForm>(key: K, value: ContactForm[K]) =>
    setEditing(e => (e ? { ...e, form: { ...e.form, [key]: value } } : e));

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Contact Matrix</div>
          <div className="page-sub">Who to contact for attendance, WFH, leave, medical and other HR matters</div>
        </div>
        {canManage && (
          <button className="btn btn-filled" onClick={openNew}><i className="ti ti-plus" /> Add Contact</button>
        )}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}
      {loading && !data && <div className="card"><div className="card-body">Loading…</div></div>}

      {data && groups.length === 0 && (
        <div className="card"><div className="card-body" style={{ color: "var(--on-variant)" }}>
          No contacts have been added yet.{canManage ? " Use Add Contact to enter the approved contact list." : " Please check with HR."}
        </div></div>
      )}

      {groups.map(group => (
        <div key={group.level} className="card mb-16">
          <div className="card-header"><div className="card-title"><i className="ti ti-stairs-up" /> {levelLabel(group.level)}</div></div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Name</th><th>Designation</th><th>Contact for</th><th>Email</th><th>Phone</th><th>Branch</th>{canManage && <th />}</tr>
              </thead>
              <tbody>
                {group.contacts.map(c => (
                  <tr key={c.id}>
                    <td><strong>{c.name}</strong>{c.department && <div style={{ fontSize: 11, color: "var(--outline)" }}>{c.department}</div>}</td>
                    <td>{c.designation || "—"}</td>
                    <td>{c.purpose || "—"}</td>
                    <td>{c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : "—"}</td>
                    <td>{c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : "—"}</td>
                    <td>{c.branch_name || "All branches"}</td>
                    {canManage && (
                      <td style={{ whiteSpace: "nowrap" }}>
                        <button className="btn btn-ghost btn-sm" onClick={() => openEdit(c)} aria-label={`Edit ${c.name}`}><i className="ti ti-pencil" /></button>
                        <button className="btn btn-ghost btn-sm" onClick={() => remove(c)} aria-label={`Remove ${c.name}`}><i className="ti ti-trash" /></button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {editing && (
        <Modal
          title={editing.id === null ? "Add Contact" : "Edit Contact"}
          onClose={() => !saving && setEditing(null)}
          footer={<>
            <button className="btn btn-ghost" onClick={() => setEditing(null)} disabled={saving}>Cancel</button>
            <button className="btn btn-filled" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save"}</button>
          </>}
        >
          <div className="form-row cols-2">
            <div className="field-group"><label className="field-label">Name *</label>
              <input className="field-input" value={editing.form.name} onChange={e => set("name", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Designation</label>
              <input className="field-input" value={editing.form.designation} onChange={e => set("designation", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Department</label>
              <input className="field-input" value={editing.form.department} onChange={e => set("department", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Contact for</label>
              <input className="field-input" placeholder="e.g. Attendance, WFH, leave" value={editing.form.purpose} onChange={e => set("purpose", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Email</label>
              <input className="field-input" type="email" value={editing.form.email} onChange={e => set("email", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Phone</label>
              <input className="field-input" value={editing.form.phone} onChange={e => set("phone", e.target.value)} /></div>
            <div className="field-group"><label className="field-label">Escalation level</label>
              <input className="field-input" type="number" min={1} value={editing.form.escalation_level}
                onChange={e => set("escalation_level", Number(e.target.value))} /></div>
            <div className="field-group"><label className="field-label">Branch</label>
              <select className="field-input" value={editing.form.branch ?? ""}
                onChange={e => set("branch", e.target.value ? Number(e.target.value) : null)}>
                <option value="">All branches</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
              </select></div>
          </div>
          {formError && <div className="field-error" role="alert">{formError}</div>}
        </Modal>
      )}
    </>
  );
}
