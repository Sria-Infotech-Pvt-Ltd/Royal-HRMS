"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { KtHandoverTask, SeparationRequest } from "@/types/separation";
import type { SeparationAccess } from "../../_access";
import { fmtDate } from "../../_workflow";
import EmployeePickerField, { type PickedEmployee } from "../../_components/EmployeePickerField";

interface Props {
  r:      SeparationRequest;
  access: SeparationAccess;
}

interface NewTaskForm {
  task: string; description: string; dueDate: string;
}

const EMPTY_FORM: NewTaskForm = { task: "", description: "", dueDate: "" };

export default function KtHandoverSection({ r, access }: Props) {
  const { showToast } = useToast();
  const { data: tasks, loading, refetch } = useFetch<KtHandoverTask[]>(API.separation.tasks(r.id));

  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<NewTaskForm>(EMPTY_FORM);
  const [assignee, setAssignee] = useState<PickedEmployee | null>(null);
  const [saving, setSaving] = useState(false);

  const canManage = access.canApprove && !r.is_own;
  const rows = tasks ?? [];
  const completed = rows.filter(t => t.is_completed).length;

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function submitTask() {
    if (!form.task.trim()) return;
    setSaving(true);
    try {
      await clientApi.post(API.separation.tasks(r.id), {
        task: form.task.trim(),
        description: form.description.trim(),
        assigned_to: assignee?.uuid || undefined,
        due_date: form.dueDate || undefined,
      });
      showToast("Handover task added.", "success");
      setForm(EMPTY_FORM);
      setAssignee(null);
      setShowAdd(false);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to add task."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function toggleComplete(task: KtHandoverTask) {
    try {
      await clientApi.patch(API.separation.taskDetail(r.id, task.id), { is_completed: !task.is_completed });
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to update task."), "error");
    }
  }

  async function deleteTask(task: KtHandoverTask) {
    if (!window.confirm(`Delete the handover task "${task.task}"?`)) return;
    try {
      await clientApi.delete(API.separation.taskDetail(r.id, task.id));
      showToast("Handover task deleted.", "success");
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to delete task."), "error");
    }
  }

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-transfer" /> KT / Handover ({completed}/{rows.length})</span>
        {canManage && !showAdd && (
          <button className="btn btn-ghost btn-sm" onClick={() => setShowAdd(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> Add Task
          </button>
        )}
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {showAdd && (
          <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
            <input className="field-input" placeholder="Task name" value={form.task} onChange={e => setForm(f => ({ ...f, task: e.target.value }))} />
            <input className="field-input" placeholder="Description (optional)" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} />
            <div className="form-row cols-2">
              <EmployeePickerField value={assignee} onChange={setAssignee} />
              <input type="date" className="field-input" value={form.dueDate} onChange={e => setForm(f => ({ ...f, dueDate: e.target.value }))} />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-filled btn-sm" onClick={submitTask} disabled={saving} suppressHydrationWarning>
                {saving ? <><i className="ti ti-loader-2 spin" /> Adding…</> : "Add"}
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => { setShowAdd(false); setForm(EMPTY_FORM); setAssignee(null); }} disabled={saving} suppressHydrationWarning>Cancel</button>
            </div>
          </div>
        )}

        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> Loading…</p>
        ) : rows.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No handover tasks added yet.</p>
        ) : (
          rows.map(t => (
            <div key={t.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{t.task}</span>
                <span className={`badge ${t.is_completed ? "badge-success" : "badge-warn"}`}>{t.is_completed ? "Completed" : "Pending"}</span>
              </div>
              {t.description && <p style={{ fontSize: 12, color: "var(--on-variant)", margin: "4px 0" }}>{t.description}</p>}
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                {t.assigned_to_name || "Unassigned"}{t.due_date ? ` · Due ${fmtDate(t.due_date)}` : ""}
              </div>
              {canManage && (
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <button className={`btn btn-sm ${t.is_completed ? "btn-outline" : "btn-success"}`} onClick={() => toggleComplete(t)} suppressHydrationWarning>
                    {t.is_completed ? "Mark Incomplete" : "Mark Complete"}
                  </button>
                  <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => deleteTask(t)} suppressHydrationWarning>
                    <i className="ti ti-trash" />
                  </button>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
