"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { JobTemplate, JobTemplatePayload } from "@/types/orgStructure";

interface Props {
  jobs: JobTemplate[];
  canEdit: boolean;
  onClose: () => void;
  onChanged: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function ManageJobTemplatesModal({ jobs, canEdit, onClose, onChanged }: Props) {
  const [name, setName] = useState("");
  const [band, setBand] = useState("");
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function addTemplate() {
    if (!name.trim()) { setAddError("Name is required."); return; }
    setAdding(true);
    setAddError(null);
    const payload: JobTemplatePayload = { name: name.trim(), band: band.trim().toUpperCase() };
    try {
      await clientApi.post(API.orgStructure.jobTemplates.list, payload);
      setName("");
      setBand("");
      onChanged();
    } catch (err: unknown) {
      setAddError((err as { message?: string })?.message ?? "Failed to create job template.");
    } finally {
      setAdding(false);
    }
  }

  async function patch(template: JobTemplate, body: Partial<JobTemplatePayload>) {
    setBusyId(template.id);
    setRowError(null);
    try {
      await clientApi.patch(API.orgStructure.jobTemplates.detail(template.id), body);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to update job template.");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(template: JobTemplate) {
    if (!window.confirm(`Delete the job template "${template.name}"? This can't be undone.`)) return;
    setBusyId(template.id);
    setRowError(null);
    try {
      await clientApi.delete(API.orgStructure.jobTemplates.detail(template.id));
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to delete job template.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-briefcase" style={{ marginRight: 8 }} />Manage job templates</>}
      onClose={onClose}
      maxWidth={560}
      size="lg"
      scrollBody
      footer={<button className="btn btn-ghost" onClick={onClose}>Close</button>}
    >
      <div style={{ fontSize: 11.5, color: "var(--outline)", marginBottom: 14 }}>
        Reusable job titles offered when adding a position. Deactivate a template to stop offering
        it for new positions without losing history on positions that already use it.
      </div>

      {canEdit && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", marginBottom: 16 }}>
          <div style={{ flex: 2 }}>
            <input
              className={`field-input${addError ? " field-error" : ""}`}
              value={name}
              onChange={e => { setName(e.target.value); setAddError(null); }}
              placeholder="e.g. Senior ABAP Consultant"
            />
            {addError && <p className="field-error-msg">{addError}</p>}
          </div>
          <div style={{ flex: 1 }}>
            <input
              className="field-input"
              style={{ fontFamily: "monospace" }}
              value={band}
              onChange={e => setBand(e.target.value)}
              placeholder="Band (L4)"
            />
          </div>
          <button className="btn btn-filled" onClick={addTemplate} disabled={adding} style={{ flexShrink: 0 }}>
            {adding ? <Spin /> : <><i className="ti ti-plus" /> Add</>}
          </button>
        </div>
      )}

      {rowError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {rowError}
        </div>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Band</th>
              <th style={{ textAlign: "center" }}>Active</th>
              {canEdit && <th style={{ textAlign: "center" }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {jobs.map(j => (
              <tr key={j.id}>
                <td style={{ fontWeight: 600, fontSize: 13 }}>{j.name}</td>
                <td style={{ fontFamily: "monospace", fontSize: 12.5 }}>{j.band || "—"}</td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={j.is_active}
                    disabled={!canEdit || busyId === j.id}
                    onChange={e => patch(j, { is_active: e.target.checked })}
                  />
                </td>
                {canEdit && (
                  <td style={{ textAlign: "center" }}>
                    <button
                      className="btn btn-ghost"
                      style={{
                        width: 28, height: 28, padding: 0, justifyContent: "center",
                        border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)",
                      }}
                      onClick={() => remove(j)}
                      disabled={busyId === j.id}
                      title="Delete job template"
                    >
                      <i className="ti ti-trash" style={{ fontSize: 13 }} />
                    </button>
                  </td>
                )}
              </tr>
            ))}
            {jobs.length === 0 && (
              <tr>
                <td colSpan={canEdit ? 4 : 3} style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)" }}>
                  No job templates yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Modal>
  );
}
