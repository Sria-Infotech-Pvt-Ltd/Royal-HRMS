"use client";

import { useCallback, useEffect, useState } from "react";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";

// ─── Types ────────────────────────────────────────────────────────────────────

type DayType = "working" | "off" | "half_day";

interface Pattern {
  id: string;
  name: string;
  policy_code: string; // internal identifier — never rendered in this UI, kept for the API payload only
  monday: DayType; tuesday: DayType; wednesday: DayType; thursday: DayType;
  friday: DayType; saturday: DayType; sunday: DayType;
  working_days_count: number;
  assigned_employee_count: number; // annotated by the backend — one aggregation query, not N+1
  is_default: boolean;
  is_active: boolean;
}

interface PageData {
  count: number; page: number; page_size: number; total_pages: number;
  results: Pattern[];
}

type FormState = {
  name: string;
  monday: DayType; tuesday: DayType; wednesday: DayType; thursday: DayType;
  friday: DayType; saturday: DayType; sunday: DayType;
  is_default: boolean;
};

const DAYS: Array<{ label: string; full: string; key: keyof Omit<FormState, "name" | "is_default"> }> = [
  { label: "Mon", full: "Monday",    key: "monday" },
  { label: "Tue", full: "Tuesday",   key: "tuesday" },
  { label: "Wed", full: "Wednesday", key: "wednesday" },
  { label: "Thu", full: "Thursday",  key: "thursday" },
  { label: "Fri", full: "Friday",    key: "friday" },
  { label: "Sat", full: "Saturday",  key: "saturday" },
  { label: "Sun", full: "Sunday",    key: "sunday" },
];

const EMPTY_FORM: FormState = {
  name: "",
  monday: "working", tuesday: "working", wednesday: "working", thursday: "working",
  friday: "working", saturday: "off", sunday: "off",
  is_default: false,
};

function daysSummary(p: Pattern): string {
  const off = DAYS.filter(d => p[d.key] === "off").map(d => tr(d.label));
  const half = DAYS.filter(d => p[d.key] === "half_day").map(d => tr(d.label));
  const parts: string[] = [...off];
  if (half.length) parts.push(...half.map(d => tr("{day} (half-day)", { day: d })));
  return parts.length ? parts.join(" • ") : tr("No off days");
}

// ─── Component ────────────────────────────────────────────────────────────────

// Compact display cap — keeps the Attendance Rules page height fixed regardless
// of how many patterns exist. Backend pagination already exists on this
// endpoint (core.pagination.paginate), so this just requests smaller pages
// instead of inventing client-side slicing.
const PAGE_SIZE = 3;

export default function WeeklyOffPatternsCard() {
  const { showToast } = useToast();
  const t = useT();
  const [pageData, setPageData] = useState<PageData | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [pageErr, setPageErr] = useState<string | null>(null);

  const [showModal, setShowModal] = useState(false);
  const [editTarget, setEditTarget] = useState<Pattern | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Pattern | null>(null);
  const [deleting, setDeleting] = useState(false);

  const fetchPatterns = useCallback(async (pg: number) => {
    setLoading(true);
    setPageErr(null);
    try {
      const res = await clientApi.get(API.attendance.weeklyDayPolicies, { params: { page: pg, page_size: PAGE_SIZE } });
      setPageData(res.data?.data ?? null);
    } catch (e: unknown) {
      setPageErr((e as { message?: string }).message ?? tr("Failed to load weekly off patterns."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPatterns(page); }, [page, fetchPatterns]);

  function openCreate() {
    setEditTarget(null);
    setForm(EMPTY_FORM);
    setSaveErr(null);
    setShowModal(true);
  }

  function openEdit(p: Pattern) {
    setEditTarget(p);
    setForm({
      name: p.name,
      monday: p.monday, tuesday: p.tuesday, wednesday: p.wednesday, thursday: p.thursday,
      friday: p.friday, saturday: p.saturday, sunday: p.sunday,
      is_default: p.is_default,
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
        // policy_code is intentionally omitted — the backend always auto-generates it
        // (WD-{n}) on create; it's immutable and never accepted on update anyway.
        name: form.name,
        monday: form.monday, tuesday: form.tuesday, wednesday: form.wednesday, thursday: form.thursday,
        friday: form.friday, saturday: form.saturday, sunday: form.sunday,
        is_default: form.is_default, is_active: true,
      };
      if (editTarget) {
        await clientApi.patch(API.attendance.weeklyDayPolicy(editTarget.id), payload);
      } else {
        await clientApi.post(API.attendance.weeklyDayPolicies, payload);
      }
      closeModal();
      fetchPatterns(page);
    } catch (e: unknown) {
      const err = e as { message?: string; response?: { data?: { message?: string } } };
      setSaveErr(err.response?.data?.message ?? err.message ?? t("Failed to save pattern."));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await clientApi.delete(API.attendance.weeklyDayPolicy(deleteTarget.id));
      setDeleteTarget(null);
      // If that was the last pattern on a page beyond the first, step back a
      // page instead of showing an empty page.
      const remaining = (pageData?.results.length ?? 1) - 1;
      const nextPage = remaining === 0 && page > 1 ? page - 1 : page;
      setPage(nextPage);
      fetchPatterns(nextPage);
    } catch (e: unknown) {
      const err = e as { message?: string; response?: { data?: { message?: string } } };
      showToast(err.response?.data?.message ?? err.message ?? t("Delete failed."), "error");
    } finally {
      setDeleting(false);
    }
  }

  const patterns = pageData?.results ?? [];

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-calendar-cog" /> {t("Weekly Off Patterns")}</div>
        <button className="btn btn-filled btn-sm" onClick={openCreate} suppressHydrationWarning>
          <i className="ti ti-plus" /> {t("Add Pattern")}
        </button>
      </div>
      <div className="card-body">
        <p className="field-label" style={{ marginBottom: 10 }}>
          {t("Configure reusable weekly-off schedules and assign them to employees from Attendance & Time → Weekly Off Assignment.")}
        </p>

        {pageErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {pageErr}</div>}

        {loading ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {t("Loading…")}
          </div>
        ) : patterns.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{t("No patterns created yet.")}</div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t("Pattern")}</th>
                  <th>{t("Weekly Off Days")}</th>
                  <th>{t("Usage")}</th>
                  <th style={{ textAlign: "right" }}>{t("Actions")}</th>
                </tr>
              </thead>
              <tbody>
                {patterns.map(p => {
                  const inUse = p.assigned_employee_count > 0;
                  const deleteBlockedReason = p.is_default
                    ? t("Assign another pattern as default before removing this one.")
                    : inUse
                      ? (p.assigned_employee_count === 1 ? t("Currently assigned to {count} employee — reassign them first.", { count: p.assigned_employee_count }) : t("Currently assigned to {count} employees — reassign them first.", { count: p.assigned_employee_count }))
                      : undefined;
                  return (
                    <tr key={p.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                          <span style={{ fontWeight: 600 }}>{p.name}</span>
                          {p.is_default && <span className="badge badge-primary" style={{ fontSize: 10 }}>{t("Default")}</span>}
                          {!p.is_active && <span className="badge badge-neutral" style={{ fontSize: 10 }}>{t("Inactive")}</span>}
                        </div>
                      </td>
                      <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{daysSummary(p)}</td>
                      <td style={{ fontSize: 12, color: "var(--on-variant)" }}>
                        {p.assigned_employee_count === 1 ? t("{count} employee", { count: p.assigned_employee_count }) : t("{count} employees", { count: p.assigned_employee_count })}
                      </td>
                      <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                        <button className="btn btn-ghost btn-sm" title={t("Edit")} onClick={() => openEdit(p)} suppressHydrationWarning aria-label={t("Edit")}>
                          <i className="ti ti-edit" />
                        </button>
                        <button
                          className="btn btn-ghost btn-sm"
                          title={deleteBlockedReason ?? t("Deactivate")}
                          style={{ color: "var(--error)" }}
                          onClick={() => setDeleteTarget(p)}
                          disabled={!!deleteBlockedReason}
                          suppressHydrationWarning
                         aria-label={t("Delete")}>
                          <i className="ti ti-trash" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Compact pagination — scoped to this card only; never shown at ≤3 patterns */}
        {!loading && pageData && pageData.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 14, marginTop: 14 }}>
            <button
              className="btn btn-ghost btn-sm"
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(p - 1, 1))}
              suppressHydrationWarning
             aria-label={t("Previous")}>
              <i className="ti ti-chevron-left" />
            </button>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              {pageData.page} / {pageData.total_pages}
            </span>
            <button
              className="btn btn-ghost btn-sm"
              disabled={page >= pageData.total_pages}
              onClick={() => setPage(p => Math.min(p + 1, pageData.total_pages))}
              suppressHydrationWarning
             aria-label={t("Next")}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        )}
      </div>

      {/* ── Create/Edit modal ────────────────────────────────────────────── */}
      {showModal && (
        <Modal
          title={<><i className="ti ti-calendar-cog" /> {editTarget ? t("Edit Pattern") : t("Add Weekly Off Pattern")}</>}
          onClose={closeModal}
          maxWidth="min(560px, 96vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={closeModal} disabled={saving} suppressHydrationWarning>{t("Cancel")}</button>
              <button className="btn btn-filled" onClick={handleSave} disabled={saving || !form.name} suppressHydrationWarning>
                {saving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {t("Saving…")}</> : t("Save Pattern")}
              </button>
            </>
          }
        >
          {saveErr && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {saveErr}</div>}

          <div className="field-group">
            <label className="field-label">{t("Pattern Name")} <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className="field-input"
              placeholder={t("e.g. Sunday Off, Weekend Off")}
              value={form.name}
              onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
              suppressHydrationWarning
            />
          </div>

          {/* policy_code (e.g. WD-004) is an internal identifier only — the backend
              auto-generates it; it's never shown or editable in this UI. */}

          <div className="field-group" style={{ marginTop: 16 }}>
            <label className="field-label">{t("Day Schedule")}</label>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(90px, 1fr))", gap: 8 }}>
              {DAYS.map(({ label, key }) => (
                <div key={key}>
                  <label style={{ fontSize: 11, color: "var(--on-variant)", display: "block", marginBottom: 2 }}>{t(label)}</label>
                  <select
                    className="field-input field-select"
                    value={form[key]}
                    onChange={e => setForm(f => ({ ...f, [key]: e.target.value as DayType }))}
                  >
                    <option value="working">{t("Working")}</option>
                    <option value="off">{t("Off")}</option>
                    <option value="half_day">{t("Half Day")}</option>
                  </select>
                </div>
              ))}
            </div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={e => setForm(f => ({ ...f, is_default: e.target.checked }))}
              suppressHydrationWarning
            />
            {t("Make this the organization default pattern")}
          </label>
        </Modal>
      )}

      {/* ── Delete confirm ───────────────────────────────────────────────── */}
      {deleteTarget && (
        <Modal
          title={<span style={{ color: "var(--error)" }}><i className="ti ti-trash" /> {t("Deactivate Pattern")}</span>}
          onClose={() => setDeleteTarget(null)}
          closeDisabled={deleting}
          maxWidth="min(420px, 94vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)} disabled={deleting} suppressHydrationWarning>{t("Cancel")}</button>
              <button className="btn btn-filled" style={{ background: "var(--error-solid)" }} onClick={handleDelete} disabled={deleting} suppressHydrationWarning>
                {deleting ? t("Deactivating…") : t("Deactivate")}
              </button>
            </>
          }
        >
          <p style={{ fontSize: 14, color: "var(--on-variant)" }}>
            {t("\"{name}\" will be deactivated. Employees currently assigned this pattern keep it until reassigned — history is preserved.", { name: deleteTarget.name })}
          </p>
        </Modal>
      )}
    </div>
  );
}
