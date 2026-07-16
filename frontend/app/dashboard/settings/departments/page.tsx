"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";

interface RoleInfo    { name: string; display_name: string }
interface Department  {
  id: number; name: string; description: string; is_active: boolean;
  created_at: string; designation_count: number; employee_count: number;
  roles: RoleInfo[];
}
interface Designation {
  id: number; name: string; department: number;
  department_name: string; is_active: boolean;
}

const BLANK_DEPT  = { name: "", description: "", is_active: true };
const BLANK_DESIG = { name: "", is_active: true };

const PALETTE = [
  { bg: "rgba(30,78,140,0.12)",  solid: "#1e4e8c", fg: "var(--primary)"  },
  { bg: "rgba(14,124,134,0.12)", solid: "#0e7c86", fg: "var(--info)"     },
  { bg: "rgba(27,138,107,0.12)", solid: "#1b8a6b", fg: "var(--success)"  },
  { bg: "rgba(181,101,29,0.12)", solid: "#b5651d", fg: "var(--warn)"     },
  { bg: "rgba(173,149,207,0.15)",solid: "#ad95cf", fg: "var(--purple)"   },
];
function pal(name: string) {
  return PALETTE[name.charCodeAt(0) % PALETTE.length];
}

// ─── Spinner ──────────────────────────────────────────────────────────────────
function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function DepartmentsPage() {
  const router    = useRouter();
  const canEdit   = usePermission("settings.edit");

  const [departments,  setDepartments]  = useState<Department[]>([]);
  const [designations, setDesignations] = useState<Designation[]>([]);
  const [selected,     setSelected]     = useState<Department | null>(null);

  const [loading,      setLoading]      = useState(true);
  const [desigLoading, setDesigLoading] = useState(false);
  const [saving,       setSaving]       = useState(false);
  const [pageError,    setPageError]    = useState<string | null>(null);
  const [saveError,    setSaveError]    = useState<string | null>(null);
  const [search,       setSearch]       = useState("");

  const [deptModal,    setDeptModal]    = useState<"add" | "edit" | null>(null);
  const [deptForm,     setDeptForm]     = useState(BLANK_DEPT);
  const [editingDept,  setEditingDept]  = useState<Department | null>(null);
  const [deptErrors,   setDeptErrors]   = useState<Record<string, string>>({});

  const [desigModal,   setDesigModal]   = useState<"add" | "edit" | null>(null);
  const [desigForm,    setDesigForm]    = useState(BLANK_DESIG);
  const [editingDesig, setEditingDesig] = useState<Designation | null>(null);
  const [desigErrors,  setDesigErrors]  = useState<Record<string, string>>({});

  // ── Data ───────────────────────────────────────────────────────────────────

  async function loadDepartments() {
    setLoading(true); setPageError(null);
    try {
      const res = await clientApi.get(API.departments.list);
      const raw = res.data?.data?.results;
      const data: Department[] = Array.isArray(raw) ? raw : [];
      setDepartments(data);
      if (selected) {
        const refreshed = data.find(d => d.id === selected.id);
        if (refreshed) setSelected(refreshed);
      }
    } catch (e: unknown) {
      setPageError((e as { message?: string }).message ?? "Failed to load.");
    } finally { setLoading(false); }
  }

  async function loadDesignations(id: number) {
    setDesigLoading(true);
    try {
      const res = await clientApi.get(API.designations.list, { params: { department: id } });
      const raw = res.data?.data?.results;
      setDesignations(Array.isArray(raw) ? raw : []);
    } catch { setDesignations([]); }
    finally  { setDesigLoading(false); }
  }

  useEffect(() => { loadDepartments(); }, []); // eslint-disable-line
  useEffect(() => {
    if (selected) loadDesignations(selected.id);
    else setDesignations([]);
  }, [selected?.id]); // eslint-disable-line

  // ── Department CRUD ────────────────────────────────────────────────────────

  function openAddDept() {
    setSaveError(null); setDeptErrors({});
    setEditingDept(null); setDeptForm(BLANK_DEPT); setDeptModal("add");
  }
  function openEditDept(d: Department) {
    setSaveError(null); setDeptErrors({});
    setEditingDept(d);
    setDeptForm({ name: d.name, description: d.description, is_active: d.is_active });
    setDeptModal("edit");
  }
  async function saveDept() {
    const errs: Record<string, string> = {};
    if (!deptForm.name.trim()) errs.name = "Department name is required.";
    if (Object.keys(errs).length) { setDeptErrors(errs); return; }
    setSaving(true); setSaveError(null);
    try {
      if (deptModal === "edit" && editingDept)
        await clientApi.put(API.departments.detail(editingDept.id), deptForm);
      else
        await clientApi.post(API.departments.list, deptForm);
      setDeptModal(null);
      await loadDepartments();
    } catch (e: unknown) {
      setSaveError((e as { message?: string }).message ?? "Failed to save.");
    } finally { setSaving(false); }
  }
  async function deleteDept(d: Department) {
    if (!window.confirm(`Delete "${d.name}"? This cannot be undone.`)) return;
    try {
      await clientApi.delete(API.departments.detail(d.id));
      if (selected?.id === d.id) setSelected(null);
      await loadDepartments();
    } catch (e: unknown) {
      setPageError((e as { message?: string }).message ?? "Failed to delete.");
    }
  }

  // ── Designation CRUD ───────────────────────────────────────────────────────

  function openAddDesig() {
    setSaveError(null); setDesigErrors({});
    setEditingDesig(null); setDesigForm(BLANK_DESIG); setDesigModal("add");
  }
  function openEditDesig(d: Designation) {
    setSaveError(null); setDesigErrors({});
    setEditingDesig(d);
    setDesigForm({ name: d.name, is_active: d.is_active }); setDesigModal("edit");
  }
  async function saveDesig() {
    const errs: Record<string, string> = {};
    if (!desigForm.name.trim()) errs.name = "Designation name is required.";
    if (Object.keys(errs).length) { setDesigErrors(errs); return; }
    setSaving(true); setSaveError(null);
    try {
      if (desigModal === "edit" && editingDesig)
        await clientApi.put(API.designations.detail(editingDesig.id), desigForm);
      else
        await clientApi.post(API.designations.list, { ...desigForm, department: selected!.id });
      setDesigModal(null);
      await Promise.all([loadDesignations(selected!.id), loadDepartments()]);
    } catch (e: unknown) {
      setSaveError((e as { message?: string }).message ?? "Failed to save.");
    } finally { setSaving(false); }
  }
  async function deleteDesig(d: Designation) {
    if (!window.confirm(`Delete designation "${d.name}"?`)) return;
    try {
      await clientApi.delete(API.designations.detail(d.id));
      await Promise.all([loadDesignations(selected!.id), loadDepartments()]);
    } catch (e: unknown) {
      setPageError((e as { message?: string }).message ?? "Failed to delete.");
    }
  }

  const filtered   = departments.filter(d => d.name.toLowerCase().includes(search.toLowerCase()));
  const totalDesig = departments.reduce((s, d) => s + d.designation_count, 0);

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Departments &amp; Designations</h1>
          <p className="page-sub">Global organisation structure — shared across all branches</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          {canEdit && (
            <button className="btn btn-filled" onClick={openAddDept}>
              <i className="ti ti-building-plus" /> Add Department
            </button>
          )}
        </div>
      </div>

      {pageError && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" /> {pageError}
          <button style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }} onClick={() => setPageError(null)}>
            <i className="ti ti-x" />
          </button>
        </div>
      )}

      {/* ── Stats bar ── */}
      <div
        className="grid grid-cols-1 sm:grid-cols-3 rounded-xl overflow-hidden border border-[var(--outline-v)] mb-6"
        style={{ gap: 1, background: "var(--outline-v)" }}
      >
        {[
          { icon: "ti-building",    color: "var(--primary)", bg: "rgba(30,78,140,0.08)",  label: "Departments",  value: departments.length },
          { icon: "ti-id-badge",    color: "var(--info)",    bg: "rgba(14,124,134,0.08)", label: "Designations", value: totalDesig },
          { icon: "ti-circle-check",color: "var(--success)", bg: "rgba(27,138,107,0.08)", label: "Active Depts", value: departments.filter(d => d.is_active).length },
        ].map((s, i) => (
          <div key={i} style={{ background: "var(--surface)", padding: "18px 22px", display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ width: 44, height: 44, borderRadius: 12, background: s.bg, display: "flex", alignItems: "center", justifyContent: "center", color: s.color, flexShrink: 0 }}>
              <i className={`ti ${s.icon}`} style={{ fontSize: 20 }} />
            </div>
            <div>
              <div style={{ fontSize: 26, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1 }}>{s.value}</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Main grid — single col on mobile, two-col on desktop ── */}
      <div className="flex flex-col md:grid md:items-start gap-5" style={{ gridTemplateColumns: "320px 1fr" }}>

        {/* ── LEFT: department list — hidden on mobile when dept selected ── */}
        <div className={`${selected ? "hidden md:block" : "block"} md:sticky md:top-5`}>
          {/* Search */}
          <div style={{ position: "relative", marginBottom: 12 }}>
            <i className="ti ti-search" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--outline)", fontSize: 15, pointerEvents: "none" }} />
            <input
              className="field-input"
              style={{ paddingLeft: 36, fontSize: 13 }}
              placeholder="Search departments…"
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>

          {/* List */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {loading ? (
              <div style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)", fontSize: 13 }}>
                <Spin /> &nbsp;Loading departments…
              </div>
            ) : filtered.length === 0 ? (
              <div style={{ textAlign: "center", padding: "32px 16px", color: "var(--on-variant)", fontSize: 13, background: "var(--surface)", borderRadius: "var(--radius-lg)", border: "1px solid var(--outline-v)" }}>
                {search ? "No departments match your search." : "No departments yet — click Add Department to get started."}
              </div>
            ) : (
              filtered.map(dept => {
                const c      = pal(dept.name);
                const active = selected?.id === dept.id;
                return (
                  <div
                    key={dept.id}
                    onClick={() => setSelected(dept)}
                    style={{
                      background: active ? "var(--surface)" : "var(--surface)",
                      border: `1.5px solid ${active ? c.solid : "var(--outline-v)"}`,
                      borderRadius: "var(--radius-lg)",
                      padding: "13px 14px",
                      cursor: "pointer",
                      boxShadow: active ? `0 2px 12px ${c.bg}` : "none",
                      transition: "all 0.15s ease",
                      position: "relative",
                      overflow: "hidden",
                    }}
                  >
                    {/* Accent strip */}
                    <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: active ? c.solid : "transparent", borderRadius: "4px 0 0 4px", transition: "background 0.15s" }} />

                    <div style={{ paddingLeft: 8, display: "flex", alignItems: "center", gap: 11 }}>
                      {/* Avatar */}
                      <div style={{
                        width: 40, height: 40, borderRadius: 11, flexShrink: 0,
                        background: c.bg, color: c.fg,
                        display: "flex", alignItems: "center", justifyContent: "center",
                        fontWeight: 800, fontSize: 16, letterSpacing: "-0.02em",
                      }}>
                        {dept.name.charAt(0).toUpperCase()}
                      </div>

                      {/* Text */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {dept.name}
                        </div>
                        <div style={{ display: "flex", gap: 6, marginTop: 4, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 11, padding: "1px 7px", borderRadius: 20, background: "var(--bg-low)", color: "var(--on-variant)" }}>
                            {dept.designation_count} designation{dept.designation_count !== 1 ? "s" : ""}
                          </span>
                          {dept.employee_count > 0 && (
                            <span style={{ fontSize: 11, padding: "1px 7px", borderRadius: 20, background: "var(--bg-low)", color: "var(--on-variant)" }}>
                              {dept.employee_count} people
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Status + actions */}
                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }} onClick={e => e.stopPropagation()}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: dept.is_active ? "var(--success)" : "var(--outline)" }} />
                        {canEdit && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              className="btn btn-ghost"
                              style={{ width: 26, height: 26, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }}
                              title="Edit" onClick={() => openEditDept(dept)}
                            >
                              <i className="ti ti-edit" style={{ fontSize: 12 }} />
                            </button>
                            <button
                              className="btn btn-ghost"
                              style={{ width: 26, height: 26, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)" }}
                              title="Delete" onClick={() => deleteDept(dept)}
                            >
                              <i className="ti ti-trash" style={{ fontSize: 12 }} />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ── RIGHT: detail panel — hidden on mobile when nothing selected ── */}
        {!selected ? (
          <div className="hidden md:flex" style={{ background: "var(--surface)", border: "1.5px dashed var(--outline-v)", borderRadius: "var(--radius-lg)", minHeight: 400, flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 40 }}>
            <div style={{ width: 64, height: 64, borderRadius: 18, background: "var(--bg-low)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <i className="ti ti-building" style={{ fontSize: 30, color: "var(--outline)" }} />
            </div>
            <p style={{ fontSize: 15, fontWeight: 600, color: "var(--on-variant)", margin: 0 }}>No department selected</p>
            <p style={{ fontSize: 13, color: "var(--outline)", margin: 0, textAlign: "center", maxWidth: 260 }}>
              Tap a department above to view and manage its designations
            </p>
          </div>
        ) : (() => {
          const c = pal(selected.name);
          return (
            <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius-lg)", overflow: "hidden" }}>

              {/* Mobile back button */}
              <div className="md:hidden px-4 pt-3 pb-0">
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setSelected(null)}
                >
                  <i className="ti ti-arrow-left" /> Back to Departments
                </button>
              </div>

              {/* Hero header */}
              <div style={{ background: `linear-gradient(135deg, ${c.bg} 0%, var(--surface) 65%)`, borderBottom: "1px solid var(--outline-v)", padding: "22px 24px" }}>
                <div className="dept-hero-row">
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
                    <div style={{ width: 56, height: 56, borderRadius: 16, background: c.bg, color: c.fg, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 22, border: `2px solid ${c.solid}22`, flexShrink: 0 }}>
                      {selected.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                        <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--on-bg)", margin: 0 }}>{selected.name}</h2>
                        <span style={{ padding: "2px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600, background: selected.is_active ? "var(--success-c)" : "var(--bg-high)", color: selected.is_active ? "var(--success)" : "var(--on-variant)" }}>
                          {selected.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      {selected.description && (
                        <p style={{ fontSize: 13, color: "var(--on-variant)", margin: "6px 0 0", lineHeight: 1.5 }}>{selected.description}</p>
                      )}
                      {/* Quick stats */}
                      <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                        {[
                          { icon: "ti-id-badge", val: `${designations.length} Designation${designations.length !== 1 ? "s" : ""}` },
                          { icon: "ti-users",    val: `${selected.employee_count} ${selected.employee_count === 1 ? "Person" : "People"}` },
                          ...(selected.roles.length > 0 ? [{ icon: "ti-shield-check", val: `${selected.roles.length} Role${selected.roles.length !== 1 ? "s" : ""}` }] : []),
                        ].map((chip, i) => (
                          <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 20, background: "var(--bg-low)", fontSize: 12, color: "var(--on-variant)", border: "1px solid var(--outline-v)" }}>
                            <i className={`ti ${chip.icon}`} style={{ fontSize: 12 }} />
                            {chip.val}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  {canEdit && (
                    <div className="dept-hero-actions">
                      <button className="btn btn-ghost btn-sm" onClick={() => openEditDept(selected)}>
                        <i className="ti ti-edit" /> Edit
                      </button>
                      <button className="btn btn-filled btn-sm" onClick={openAddDesig}>
                        <i className="ti ti-plus" /> Add Designation
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Roles in this dept */}
              {selected.roles.length > 0 && (
                <div style={{ padding: "14px 24px", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--outline)", textTransform: "uppercase", letterSpacing: "0.06em", flexShrink: 0 }}>Roles</span>
                  {selected.roles.map(r => (
                    <span key={r.name} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 11px", borderRadius: 20, fontSize: 12, fontWeight: 500, background: "rgba(30,78,140,0.08)", color: "var(--primary)", border: "1px solid rgba(30,78,140,0.14)" }}>
                      <i className="ti ti-shield-check" style={{ fontSize: 11 }} />
                      {r.display_name}
                    </span>
                  ))}
                </div>
              )}

              {/* Designations */}
              <div style={{ padding: 24 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
                    Designations
                    <span style={{ marginLeft: 8, padding: "1px 8px", borderRadius: 20, fontSize: 11, fontWeight: 600, background: "var(--bg-high)", color: "var(--on-variant)" }}>
                      {desigLoading ? "…" : designations.length}
                    </span>
                  </div>
                </div>

                {desigLoading ? (
                  <div style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)", fontSize: 13 }}>
                    <Spin /> &nbsp;Loading…
                  </div>
                ) : designations.length === 0 ? (
                  <div style={{ textAlign: "center", padding: "36px 0", color: "var(--on-variant)", border: "1.5px dashed var(--outline-v)", borderRadius: "var(--radius-lg)" }}>
                    <i className="ti ti-id-badge" style={{ fontSize: 32, display: "block", marginBottom: 8, color: "var(--outline)" }} />
                    <p style={{ fontSize: 13, margin: 0 }}>No designations yet</p>
                    {canEdit && (
                      <button className="btn btn-ghost" style={{ marginTop: 12, fontSize: 12 }} onClick={openAddDesig}>
                        <i className="ti ti-plus" /> Add the first one
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(min(210px, 100%), 1fr))" }}>
                    {designations.map(d => (
                      <div
                        key={d.id}
                        style={{
                          border: "1px solid var(--outline-v)", borderRadius: "var(--radius-lg)",
                          padding: "14px 16px", background: "var(--bg-low)",
                          display: "flex", flexDirection: "column", gap: 10,
                          transition: "box-shadow 0.15s, border-color 0.15s",
                        }}
                      >
                        {/* Top row */}
                        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                          <div style={{ width: 34, height: 34, borderRadius: 9, background: c.bg, color: c.fg, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14 }}>
                            {d.name.charAt(0).toUpperCase()}
                          </div>
                          {canEdit && (
                            <div style={{ display: "flex", gap: 4 }}>
                              <button
                                className="btn btn-ghost"
                                style={{ width: 26, height: 26, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, background: "var(--surface)" }}
                                title="Edit" onClick={() => openEditDesig(d)}
                              >
                                <i className="ti ti-edit" style={{ fontSize: 12 }} />
                              </button>
                              <button
                                className="btn btn-ghost"
                                style={{ width: 26, height: 26, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)", background: "var(--surface)" }}
                                title="Delete" onClick={() => deleteDesig(d)}
                              >
                                <i className="ti ti-trash" style={{ fontSize: 12 }} />
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Name */}
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", lineHeight: 1.3 }}>
                          {d.name}
                        </div>

                        {/* Status */}
                        <span style={{ alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 5, padding: "2px 9px", borderRadius: 20, fontSize: 11, fontWeight: 500, background: d.is_active ? "var(--success-c)" : "var(--bg-high)", color: d.is_active ? "var(--success)" : "var(--on-variant)" }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: d.is_active ? "var(--success)" : "var(--outline)", display: "inline-block" }} />
                          {d.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })()}
      </div>

      {/* ── Department modal ── */}
      {deptModal && (
        <div className="modal-overlay open">
          <div className="modal" style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-building-plus" style={{ marginRight: 8 }} />
                {deptModal === "add" ? "New Department" : `Edit: ${editingDept?.name}`}
              </div>
              <button className="modal-close" onClick={() => setDeptModal(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {saveError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {saveError}</div>}
              <div className="field-group mb-16">
                <label className="field-label">Department Name *</label>
                <input
                  className={`field-input${deptErrors.name ? " field-error" : ""}`}
                  value={deptForm.name}
                  onChange={e => { setDeptErrors(p => { const n = {...p}; delete n.name; return n; }); setDeptForm(p => ({...p, name: e.target.value})); }}
                  placeholder="e.g. Engineering"
                  maxLength={100} autoFocus
                />
                {deptErrors.name && <p className="field-error-msg">{deptErrors.name}</p>}
              </div>
              <div className="field-group mb-16">
                <label className="field-label">Description <span style={{ color: "var(--outline)", fontWeight: 400 }}>(optional)</span></label>
                <textarea
                  className="field-input"
                  value={deptForm.description}
                  onChange={e => setDeptForm(p => ({...p, description: e.target.value}))}
                  placeholder="What does this department do?"
                  style={{ minHeight: 76 }}
                />
              </div>
              <label className="module-check">
                <input type="checkbox" checked={deptForm.is_active} onChange={e => setDeptForm(p => ({...p, is_active: e.target.checked}))} />
                <span>Active</span>
              </label>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setDeptModal(null)}>Cancel</button>
              <button className="btn btn-filled" onClick={saveDept} disabled={saving}>
                {saving ? <><Spin />&nbsp;{deptModal === "add" ? "Creating…" : "Saving…"}</> : deptModal === "add" ? "Create Department" : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Designation modal ── */}
      {desigModal && (
        <div className="modal-overlay open">
          <div className="modal" style={{ maxWidth: 440 }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-id-badge" style={{ marginRight: 8 }} />
                {desigModal === "add" ? `Add Designation` : `Edit Designation`}
              </div>
              <button className="modal-close" onClick={() => setDesigModal(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {selected && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16, padding: "8px 12px", background: "var(--bg-low)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--on-variant)" }}>
                  <i className="ti ti-building" style={{ fontSize: 14 }} />
                  Department: <strong style={{ color: "var(--on-bg)" }}>{selected.name}</strong>
                </div>
              )}
              {saveError && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {saveError}</div>}
              <div className="field-group mb-16">
                <label className="field-label">Designation Name *</label>
                <input
                  className={`field-input${desigErrors.name ? " field-error" : ""}`}
                  value={desigForm.name}
                  onChange={e => { setDesigErrors(p => { const n = {...p}; delete n.name; return n; }); setDesigForm(p => ({...p, name: e.target.value})); }}
                  placeholder="e.g. Senior Engineer"
                  maxLength={100} autoFocus
                />
                {desigErrors.name && <p className="field-error-msg">{desigErrors.name}</p>}
              </div>
              <label className="module-check">
                <input type="checkbox" checked={desigForm.is_active} onChange={e => setDesigForm(p => ({...p, is_active: e.target.checked}))} />
                <span>Active</span>
              </label>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setDesigModal(null)}>Cancel</button>
              <button className="btn btn-filled" onClick={saveDesig} disabled={saving}>
                {saving ? <><Spin />&nbsp;{desigModal === "add" ? "Adding…" : "Saving…"}</> : desigModal === "add" ? "Add Designation" : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
