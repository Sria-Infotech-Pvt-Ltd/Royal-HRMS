"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import Modal from "@/components/Modal";
import { STATUS_LABEL, apiError, type AssignmentRow, type Course, type TrainingStatus } from "@/lib/training";
import { CourseTable, ProgressTable } from "./_components/TrainingTables";

interface Dashboard {
  total_courses: number; active_courses: number; employees_assigned: number; assigned: number; completed: number;
  in_progress: number; not_started: number; overdue: number; failed: number; assessment_passed: number;
  assessment_failed: number; completion_percent: number;
}

type Tab = "courses" | "reports";

function Stat({ label, value, icon, tone }: { label: string; value: number | string; icon: string; tone?: string }) {
  return (
    <div className="card card-body" style={{ padding: 14, display: "flex", gap: 12, alignItems: "center" }}>
      <i className={`ti ${icon}`} style={{ fontSize: 22, color: tone ?? "var(--primary)" }} />
      <div>
        <div style={{ fontSize: 20, fontWeight: 700, color: "var(--on-bg)" }}>{value}</div>
        <div className="text-[12px] text-[var(--on-variant)]">{label}</div>
      </div>
    </div>
  );
}

export default function TrainingPage() {
  const router = useRouter();
  const canCreate = usePermission("training.create");
  const canReports = usePermission("training.view_reports");
  const [tab, setTab] = useState<Tab>("courses");
  const [search, setSearch] = useState("");
  const [showArchived, setShowArchived] = useState(false);

  const { data: dash } = useFetch<Dashboard>(API.training.dashboard);
  const { data: courses, loading, error } = useFetch<Course[]>(
    `${API.training.courses}?archived=${showArchived ? 1 : 0}`);

  const shown = useMemo(() => (courses ?? []).filter(c =>
    !search || `${c.title} ${c.category}`.toLowerCase().includes(search.toLowerCase())), [courses, search]);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Training &amp; Learning</div>
          <div className="page-sub">Courses, assignments, progress and assessment results.</div>
        </div>
        <div className="page-actions">
          {canCreate && <CreateCourseButton onCreated={id => router.push(`/dashboard/training/${id}`)} />}
        </div>
      </div>

      {dash && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12, marginBottom: 16 }}>
          <Stat label="Active courses" value={`${dash.active_courses} / ${dash.total_courses}`} icon="ti-books" />
          <Stat label="Employees assigned" value={dash.employees_assigned} icon="ti-users" />
          <Stat label="Completed" value={`${dash.completed} (${dash.completion_percent}%)`} icon="ti-circle-check" tone="var(--success, #16a34a)" />
          <Stat label="In progress" value={dash.in_progress} icon="ti-progress" />
          <Stat label="Overdue" value={dash.overdue} icon="ti-alarm" tone="#d97706" />
          <Stat label="Assessment pass / fail" value={`${dash.assessment_passed} / ${dash.assessment_failed}`} icon="ti-clipboard-check" />
        </div>
      )}

      <div className="tabs">
        <button className={`tab${tab === "courses" ? " active" : ""}`} onClick={() => setTab("courses")}>
          <i className="ti ti-books" style={{ marginRight: 5 }} />Courses
        </button>
        {canReports && (
          <button className={`tab${tab === "reports" ? " active" : ""}`} onClick={() => setTab("reports")}>
            <i className="ti ti-report-analytics" style={{ marginRight: 5 }} />Reports
          </button>
        )}
      </div>

      {tab === "courses" && (
        <div className="card card-body">
          <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "center" }}>
            <input className="field-input" style={{ maxWidth: 280 }} placeholder="Search courses" value={search}
                   onChange={e => setSearch(e.target.value)} aria-label="Search courses" />
            <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
              <input type="checkbox" checked={showArchived} onChange={e => setShowArchived(e.target.checked)} />
              Show archived
            </label>
          </div>
          {loading && <div className="text-[13px] text-[var(--on-variant)]">Loading courses…</div>}
          {error && <div className="alert alert-error">{error}</div>}
          {!loading && !error && shown.length === 0 && (
            <div className="text-[13px] text-[var(--on-variant)] py-6 text-center">
              No courses yet.{canCreate ? " Create the first one." : ""}
            </div>
          )}
          <CourseTable courses={shown} onOpen={id => router.push(`/dashboard/training/${id}`)} />
        </div>
      )}

      {tab === "reports" && canReports && <ReportsPanel courses={courses ?? []} />}
    </div>
  );
}

function CreateCourseButton({ onCreated }: { onCreated: (id: string) => void }) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");
  const { showToast } = useToast();

  async function create() {
    if (!title.trim()) { setErr("Give the course a title."); return; }
    setSaving(true);
    setErr("");
    try {
      const res = await clientApi.post<{ data: Course }>(API.training.courses, { title: title.trim(), category });
      showToast("Course created.", "success");
      onCreated(res.data.data.id);
    } catch (e) {
      showToast(apiError(e, "Failed to create the course."), "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <button className="btn btn-filled" onClick={() => { setOpen(true); setTitle(""); setCategory(""); setErr(""); }}>
        <i className="ti ti-plus" /> New Course
      </button>
      {open && (
        <Modal title="New Training Course" onClose={() => setOpen(false)} maxWidth={440}
               footer={<>
                 <button className="btn btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
                 <button className="btn btn-filled" onClick={create} disabled={saving}>{saving ? "Creating…" : "Create"}</button>
               </>}>
          {err && <div className="alert alert-error mb-16">{err}</div>}
          <div className="field-group mb-16">
            <label className="field-label" htmlFor="nc-title">Title *</label>
            <input id="nc-title" className="field-input" value={title} maxLength={200} onChange={e => setTitle(e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="nc-cat">Category</label>
            <input id="nc-cat" className="field-input" value={category} maxLength={100} placeholder="e.g. Safety, Compliance"
                   onChange={e => setCategory(e.target.value)} />
          </div>
        </Modal>
      )}
    </>
  );
}

const STATUS_FILTERS: (TrainingStatus | "")[] = ["", "assigned", "in_progress", "completed", "overdue", "failed"];

function ReportsPanel({ courses }: { courses: Course[] }) {
  const [f, setF] = useState({ course: "", status: "", department: "", branch: "", from: "", to: "" });
  const { data: picker } = useFetch<{ departments: string[]; branches: string[] }>(API.training.employees);
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const { data: rows, loading, error } = useFetch<AssignmentRow[]>(`${API.training.reports}${query ? `?${query}` : ""}`);
  const [exporting, setExporting] = useState(false);

  async function exportCsv() {
    setExporting(true);
    try {
      const res = await clientApi.get(`${API.training.reports}?${query}${query ? "&" : ""}export=csv`, { responseType: "blob" });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "training-report.csv";
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  }

  const sel = (key: keyof typeof f, label: string, options: { value: string; label: string }[]) => (
    <div className="field-group">
      <label className="field-label" htmlFor={`rf-${key}`}>{label}</label>
      <select id={`rf-${key}`} className="field-input field-select" value={f[key]} onChange={e => setF({ ...f, [key]: e.target.value })}>
        <option value="">All</option>
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );

  return (
    <div className="card card-body" data-testid="training-reports">
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
        {sel("course", "Course", courses.map(c => ({ value: c.id, label: c.title })))}
        {sel("status", "Status", STATUS_FILTERS.filter(Boolean).map(s => ({ value: s, label: STATUS_LABEL[s as TrainingStatus] })))}
        {sel("department", "Department", (picker?.departments ?? []).map(d => ({ value: d, label: d })))}
        {sel("branch", "Branch", (picker?.branches ?? []).map(b => ({ value: b, label: b })))}
        <div className="field-group">
          <label className="field-label" htmlFor="rf-from">Assigned from</label>
          <input id="rf-from" type="date" className="field-input" value={f.from} onChange={e => setF({ ...f, from: e.target.value })} />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="rf-to">Assigned to</label>
          <input id="rf-to" type="date" className="field-input" value={f.to} onChange={e => setF({ ...f, to: e.target.value })} />
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", margin: "12px 0" }}>
        <span className="text-[12px] text-[var(--on-variant)]">{rows ? `${rows.length} record(s)` : ""}</span>
        <button className="btn btn-ghost" onClick={exportCsv} disabled={exporting || !rows?.length}>
          <i className="ti ti-download" /> {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>
      {loading && <div className="text-[13px] text-[var(--on-variant)]">Loading…</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {rows && rows.length > 0 && <ProgressTable rows={rows} showCourse />}
      {rows && rows.length === 0 && <div className="text-[13px] text-[var(--on-variant)] py-4">No matching records.</div>}
    </div>
  );
}

