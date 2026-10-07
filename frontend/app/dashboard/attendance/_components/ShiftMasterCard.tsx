"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import Modal from "@/components/Modal";
import type { WorkingHoursPolicy, WorkingHoursPolicyForm } from "@/types/workingHours";
import type { AttendanceSettingsApiResponse } from "@/types/attendanceSettings";

interface PageData {
  count: number; page: number; page_size: number; total_pages: number;
  results: WorkingHoursPolicy[];
}

const EMPTY_FORM: WorkingHoursPolicyForm = {
  name: "",
  policy_code: "",
  description: "",
  start_time: "09:00",
  end_time: "18:00",
  break_duration: 30,
  grace_period: 15,
  standard_working_hours: 0,
  minimum_working_hours: "4.00",
  maximum_working_hours: "9.00",
  is_default: false,
  is_active: true,
};

function toHHMM(v: string | undefined): string {
  return v ? v.slice(0, 5) : "";
}

// Compact display cap — keeps the Attendance Rules page height fixed regardless
// of how many shifts exist, same pattern as WeeklyOffPatternsCard.
const PAGE_SIZE = 5;

export default function ShiftMasterCard() {
  const [pageData, setPageData] = useState<PageData | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [pageErr, setPageErr] = useState<string | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState<WorkingHoursPolicy | null>(null);
  const [form, setForm] = useState<WorkingHoursPolicyForm>(EMPTY_FORM);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<WorkingHoursPolicy | null>(null);
  const [deleting, setDeleting] = useState(false);

  // Read-only display of the existing global default (Settings -> Attendance
  // Rules -> Working Hours) — NOT a WorkingHoursPolicy row, and this card
  // never edits it. Shown so an admin sees the full shift picture ("General"
  // alongside any named shifts) in one place. Gracefully hidden if this
  // viewer doesn't hold settings.view (a narrower permission than
  // attendance.view, which gates the rest of this tab).
  const { data: globalSettings } = useFetch<AttendanceSettingsApiResponse>(API.attendance.settings);
  const globalWorkingHours = globalSettings?.working_hours;

  const fetchPolicies = useCallback(async (pg: number) => {
    setLoading(true);
    setPageErr(null);
    try {
      const res = await clientApi.get(API.attendance.workingHoursPolicies, { params: { page: pg, page_size: PAGE_SIZE, is_active: true } });
      setPageData(res.data?.data ?? null);
    } catch (e: unknown) {
      setPageErr((e as { message?: string }).message ?? "Failed to load shifts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPolicies(page); }, [page, fetchPolicies]);

  function openCreate() {
    setEditTarget(null);
    setForm(EMPTY_FORM);
    setSaveErr(null);
    setShowModal(true);
  }

  function openEdit(p: WorkingHoursPolicy) {
    setEditTarget(p);
    setForm({
      name: p.name,
      policy_code: p.policy_code,
      description: p.description,
      start_time: toHHMM(p.start_time),
      end_time: toHHMM(p.end_time),
      break_duration: p.break_duration,
      grace_period: p.grace_period,
      standard_working_hours: p.standard_working_hours,
      minimum_working_hours: p.minimum_working_hours,
      maximum_working_hours: p.maximum_working_hours,
      is_default: p.is_default,
      is_active: p.is_active,
    });
    setSaveErr(null);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setEditTarget(null);
  }

  async function handleSave() {
    setSaving(true);
    setSaveErr(null);
    try {
      const payload = {
        // policy_code is intentionally omitted on create — the backend
        // auto-generates it (WH-{n}); kept read-only on edit too.
        name: form.name,
        description: form.description,
        start_time: `${form.start_time}:00`,
        end_time: `${form.end_time}:00`,
        break_duration: form.break_duration,
        grace_period: form.grace_period,
        minimum_working_hours: form.minimum_working_hours,
        maximum_working_hours: form.maximum_working_hours,
        is_default: form.is_default,
        is_active: true,
      };
      if (editTarget) {
        await clientApi.patch(API.attendance.workingHoursPolicy(editTarget.id), payload);
      } else {
        await clientApi.post(API.attendance.workingHoursPolicies, payload);
      }
      closeModal();
      fetchPolicies(page);
    } catch (e: unknown) {
      const err = e as { message?: string; response?: { data?: { message?: string } } };
      setSaveErr(err.response?.data?.message ?? err.message ?? "Failed to save shift.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await clientApi.delete(API.attendance.workingHoursPolicy(deleteTarget.id));
      setDeleteTarget(null);
      const remaining = (pageData?.results.length ?? 1) - 1;
      const nextPage = remaining === 0 && page > 1 ? page - 1 : page;
      setPage(nextPage);
      fetchPolicies(nextPage);
    } catch (e: unknown) {
      const err = e as { message?: string; response?: { data?: { message?: string } } };
      alert(err.response?.data?.message ?? err.message ?? "Delete failed.");
    } finally {
      setDeleting(false);
    }
  }

  const policies = pageData?.results ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clock-cog" /> Shifts</div>
        <button className="btn btn-filled btn-sm" onClick={openCreate} suppressHydrationWarning>
          <i className="ti ti-plus" /> Add Shift
        </button>
      </div>
      <div className="card-body">
        <p className="field-label" style={{ marginBottom: 10 }}>
          Configure named shift timings and assign them to employees from
          Attendance &amp; Time → Shift Assignment. Employees with no shift
          assigned keep using the global default below.
        </p>

        {globalWorkingHours && (
          <div
            style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              padding: "10px 14px", borderRadius: 8, background: "var(--surface-variant)",
              marginBottom: 14, fontSize: 13,
            }}
          >
            <span>
              <strong>General / Default</strong> — {toHHMM(globalWorkingHours.shift_start)} to {toHHMM(globalWorkingHours.shift_end)}
            </span>
            <span style={{ color: "var(--on-variant)", fontSize: 12 }}>
              Applies to every employee with no shift assigned below · edit under Settings → Attendance Rules
            </span>
          </div>
        )}

        {pageErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {pageErr}</div>}

        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading…
          </div>
        ) : policies.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No named shifts created yet.</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Shift</th>
                  <th>Timing</th>
                  <th>Break</th>
                  <th>Grace Period</th>
                  <th style={{ textAlign: "right" }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {policies.map(p => (
                  <tr key={p.id}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 600 }}>{p.name}</span>
                        {p.is_default && <span className="badge badge-primary" style={{ fontSize: 10 }}>Default</span>}
                      </div>
                    </td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{toHHMM(p.start_time)} – {toHHMM(p.end_time)}</td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{p.break_duration} min</td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{p.grace_period} min</td>
                    <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                      <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => openEdit(p)} suppressHydrationWarning>
                        <i className="ti ti-edit" />
                      </button>
                      <button
                        className="btn btn-ghost btn-sm"
                        title={p.is_default ? "Assign another shift as default before removing this one." : "Deactivate"}
                        style={{ color: "var(--error)" }}
                        onClick={() => setDeleteTarget(p)}
                        disabled={p.is_default}
                        suppressHydrationWarning
                      >
                        <i className="ti ti-trash" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && pageData && pageData.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, marginTop: 14 }}>
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))} suppressHydrationWarning>
              <i className="ti ti-chevron-left" />
            </button>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{pageData.page} / {pageData.total_pages}</span>
            <button className="btn btn-ghost btn-sm" disabled={page >= pageData.total_pages} onClick={() => setPage(p => Math.min(p + 1, pageData.total_pages))} suppressHydrationWarning>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        )}
      </div>

      {/* ── Create/Edit modal ────────────────────────────────────────────── */}
      {showModal && (
        <Modal
          title={<><i className="ti ti-clock-cog" /> {editTarget ? "Edit Shift" : "Add Shift"}</>}
          onClose={closeModal}
          maxWidth="min(520px, 96vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeModal} disabled={saving} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled" onClick={handleSave} disabled={saving || !form.name || !form.start_time || !form.end_time} suppressHydrationWarning>
                {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : "Save Shift"}
              </button>
            </>
          }
        >
          {saveErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {saveErr}</div>}

          <div className="field-group">
            <label className="field-label">Shift Name <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className="field-input"
              placeholder="e.g. SGT/ICT Shift, UK Shift"
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              suppressHydrationWarning
            />
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Start Time</label>
              <input type="time" className="field-input" value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} />
            </div>
            <div className="field-group">
              <label className="field-label">End Time</label>
              <input type="time" className="field-input" value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} />
            </div>
          </div>

          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Break Duration (min)</label>
              <input type="number" min={0} className="field-input" value={form.break_duration} onChange={e => setForm(f => ({ ...f, break_duration: Number(e.target.value) }))} />
            </div>
            <div className="field-group">
              <label className="field-label">Grace Period (min)</label>
              <input type="number" min={0} className="field-input" value={form.grace_period} onChange={e => setForm(f => ({ ...f, grace_period: Number(e.target.value) }))} />
            </div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={e => setForm(f => ({ ...f, is_default: e.target.checked }))}
              suppressHydrationWarning
            />
            Make this the organization default shift
          </label>
        </Modal>
      )}

      {/* ── Delete confirm ───────────────────────────────────────────────── */}
      {deleteTarget && (
        <Modal
          title={<span style={{ color: "var(--error)" }}><i className="ti ti-trash" /> Deactivate Shift</span>}
          onClose={() => setDeleteTarget(null)}
          closeDisabled={deleting}
          maxWidth="min(420px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)} disabled={deleting} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled" style={{ background: "var(--error)" }} onClick={handleDelete} disabled={deleting} suppressHydrationWarning>
                {deleting ? "Deactivating…" : "Deactivate"}
              </button>
            </>
          }
        >
          <p style={{ fontSize: 14, color: "var(--on-variant)" }}>
            &quot;{deleteTarget.name}&quot; will be deactivated. Employees currently assigned this
            shift keep it until reassigned — history is preserved.
          </p>
        </Modal>
      )}
    </div>
  );
}
