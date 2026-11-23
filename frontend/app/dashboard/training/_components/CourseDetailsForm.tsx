"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import {
  apiError, courseFormPayload, courseToForm, todayIso, validateCourse, type Course, type CourseForm,
} from "@/lib/training";

interface AssessmentOption { id: string; title: string; questions: number; pass_percentage: number }

export default function CourseDetailsForm({ course, canEdit, onSaved, onContinue, onClose }: {
  course: Course; canEdit: boolean; onSaved: () => void;
  /** After "Save & Continue" — the next step (Materials). */
  onContinue?: () => void;
  /** After "Save & Close" — back to the course list. */
  onClose?: () => void;
}) {
  const canLink = usePermission("training.manage_assessments");
  const canAssign = usePermission("training.assign");
  const canCreateAssessment = usePermission("assessments.create");
  const { data: assessments, refetch: refetchAssessments } =
    useFetch<AssessmentOption[]>(canLink ? API.training.assessments : null);
  // "+ New Assessment" opens the Assessments module in a new tab (the course
  // form keeps its unsaved edits); reload the list when the user comes back.
  useEffect(() => {
    if (!canLink) return;
    const onFocus = () => refetchAssessments();
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [canLink, refetchAssessments]);
  const { data: picker } = useFetch<{ departments: string[]; branches: string[] }>(
    canAssign ? API.training.employees : null);
  const [draft, setDraft] = useState<CourseForm | null>(null);
  const form = draft ?? courseToForm(course);
  const [saving, setSaving] = useState(false);
  const { showToast } = useToast();
  const [thumbKey, setThumbKey] = useState(0);
  const errors = validateCourse(form);

  function set<K extends keyof CourseForm>(k: K, v: CourseForm[K]) {
    setDraft({ ...form, [k]: v });
  }

  async function save(next: "continue" | "close") {
    if (Object.keys(errors).length) return;
    setSaving(true);
    try {
      await clientApi.patch(API.training.course(course.id), courseFormPayload(form, canLink));
      setDraft(null);
      showToast("Course saved.", "success");
      onSaved();
      if (next === "continue") onContinue?.();
      else onClose?.();
    } catch (e) {
      showToast(apiError(e, "Failed to save the course."), "error");
    } finally {
      setSaving(false);
    }
  }

  async function uploadThumb(file: File | undefined) {
    if (!file) return;
    const fd = new FormData();
    fd.append("thumbnail", file);
    try {
      await clientApi.post(API.training.thumbnail(course.id), fd, { timeout: 60000 });
      setThumbKey(k => k + 1);
      showToast("Thumbnail updated.", "success");
      onSaved();
    } catch (e) {
      showToast(apiError(e, "Failed to upload the thumbnail."), "error");
    }
  }

  const text = (k: "title" | "category" | "trainer_name" | "duration_minutes", label: string, extra = {}) => (
    <div className="field-group">
      <label className="field-label" htmlFor={`cf-${k}`}>{label}</label>
      <input id={`cf-${k}`} className="field-input" value={form[k]} disabled={!canEdit}
             onChange={e => set(k, e.target.value)} {...extra} />
      {errors[k] && <div className="text-[12px] text-red-600 mt-1">{errors[k]}</div>}
    </div>
  );
  const date = (k: "start_date" | "deadline", label: string) => (
    <div className="field-group">
      <label className="field-label" htmlFor={`cf-${k}`}>{label}</label>
      <input id={`cf-${k}`} type="date" className="field-input" value={form[k]} disabled={!canEdit}
             onChange={e => set(k, e.target.value)} />
      {errors[k] && <div className="text-[12px] text-red-600 mt-1">{errors[k]}</div>}
      {k === "deadline" && !errors[k] && form.deadline && form.deadline < todayIso() && (
        <div className="text-[12px] mt-1" style={{ color: "var(--warning, #b45309)" }} role="status">
          This deadline has passed — new assignments won&apos;t get it as their due date.
        </div>
      )}
    </div>
  );
  const toggleList = (k: "new_joiner_branches" | "new_joiner_departments", value: string, on: boolean) =>
    set(k, on ? [...new Set([...form[k], value])] : form[k].filter(x => x !== value));

  return (
    <div className="card card-body" data-testid="course-details">
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "flex-start", marginBottom: 14 }}>
        <div style={{ width: 160, height: 90, borderRadius: 10, overflow: "hidden", background: "var(--bg-low)",
                      display: "flex", alignItems: "center", justifyContent: "center" }}>
          {course.has_thumbnail
            // eslint-disable-next-line @next/next/no-img-element
            ? <img key={thumbKey} src={`${API_BASE}${API.training.thumbnailFile(course.id)}?v=${thumbKey}`} alt=""
                   style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            : <i className="ti ti-photo" style={{ fontSize: 28, color: "var(--on-variant)" }} />}
        </div>
        {canEdit && (
          <label className="btn btn-ghost" style={{ cursor: "pointer" }}>
            <i className="ti ti-upload" /> Thumbnail (PNG/JPG, 2 MB)
            <input type="file" accept="image/png,image/jpeg" hidden onChange={e => uploadThumb(e.target.files?.[0])} />
          </label>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        {text("title", "Title *", { maxLength: 200 })}
        {text("category", "Category", { maxLength: 100 })}
        {text("trainer_name", "Trainer / owner", { maxLength: 150 })}
        {text("duration_minutes", "Duration (minutes)", { inputMode: "numeric" })}
        {date("start_date", "Start date")}
        {date("deadline", "Completion deadline")}
      </div>
      <div className="field-group" style={{ marginTop: 14 }}>
        <label className="field-label" htmlFor="cf-desc">Description</label>
        <textarea id="cf-desc" className="field-input" rows={3} value={form.description} disabled={!canEdit}
                  onChange={e => set("description", e.target.value)} />
      </div>
      <div style={{ display: "flex", gap: 20, marginTop: 12, fontSize: 13, flexWrap: "wrap" }}>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={form.is_mandatory} disabled={!canEdit} onChange={e => set("is_mandatory", e.target.checked)} />
          Mandatory
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={form.is_active} disabled={!canEdit} onChange={e => set("is_active", e.target.checked)} />
          Active
        </label>
      </div>

      <div style={{ borderTop: "1px solid var(--outline-v)", marginTop: 18, paddingTop: 14 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>Assessment</div>
        <div className="text-[12px] text-[var(--on-variant)] mb-2">
          An existing MCQ assessment from the Assessments module. It unlocks after the required materials; its pass mark
          and attempt limit apply. Taking it here does not affect onboarding assessments.
        </div>
        {canLink ? (
          <>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <select className="field-input field-select" style={{ maxWidth: 420 }} value={form.assessment} disabled={!canEdit}
                      onChange={e => set("assessment", e.target.value)} aria-label="Linked assessment">
                <option value="">— No assessment —</option>
                {course.assessment && !assessments?.some(a => a.id === course.assessment?.id) && (
                  <option value={course.assessment.id}>{course.assessment.title}</option>
                )}
                {(assessments ?? []).map(a => (
                  <option key={a.id} value={a.id}>{a.title} ({a.questions} questions, pass {a.pass_percentage}%)</option>
                ))}
              </select>
              {canEdit && canCreateAssessment && (
                <a className="btn btn-ghost btn-sm" href="/dashboard/assessments?create=1" target="_blank" rel="noopener"
                   title="Create a new assessment in the Assessments module (opens in a new tab)">
                  <i className="ti ti-plus" /> New Assessment
                </a>
              )}
            </div>
            {canEdit && canCreateAssessment && (
              <div className="text-[12px] text-[var(--on-variant)] mt-1">
                A new assessment appears in this list once it is active and has at least one question.
              </div>
            )}
          </>
        ) : (
          <div className="text-[13px]">{course.assessment ? course.assessment.title : "None"}</div>
        )}
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, marginTop: 12 }}>
          <input type="checkbox" checked={form.videos_optional} disabled={!canEdit}
                 onChange={e => set("videos_optional", e.target.checked)} />
          <strong>Video watching optional</strong> — employees can go straight to the assessment
        </label>
        <div className="text-[12px] text-[var(--on-variant)] mt-1">
          Ticked: videos don&apos;t block the assessment, and passing it completes the course. Documents marked
          Required still have to be read. Unticked: required videos must be watched before the assessment.
        </div>
        {errors.videos_optional && <div className="text-[12px] text-red-600 mt-1">{errors.videos_optional}</div>}
      </div>

      <div style={{ borderTop: "1px solid var(--outline-v)", marginTop: 18, paddingTop: 14 }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600, fontSize: 14 }}>
          <input type="checkbox" checked={form.auto_assign_new_joiners} disabled={!canEdit}
                 onChange={e => set("auto_assign_new_joiners", e.target.checked)} />
          Assign automatically to new joiners
        </label>
        <div className="text-[12px] text-[var(--on-variant)] mt-1">
          Assigned when an employee&apos;s onboarding is approved from now on. Existing employees are not assigned
          automatically — use the Assign tab.
        </div>
        {form.auto_assign_new_joiners && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14, marginTop: 10 }}>
            <div className="field-group">
              <label className="field-label" htmlFor="cf-nj-days">Complete within (days)</label>
              <input id="cf-nj-days" className="field-input" inputMode="numeric" value={form.new_joiner_deadline_days}
                     disabled={!canEdit} onChange={e => set("new_joiner_deadline_days", e.target.value)} />
              {errors.new_joiner_deadline_days && <div className="text-[12px] text-red-600 mt-1">{errors.new_joiner_deadline_days}</div>}
            </div>
            {(["new_joiner_branches", "new_joiner_departments"] as const).map(k => {
              const options = k === "new_joiner_branches" ? picker?.branches : picker?.departments;
              const all = [...new Set([...(options ?? []), ...form[k]])];
              return (
                <div className="field-group" key={k}>
                  <div className="field-label">{k === "new_joiner_branches" ? "Branches" : "Departments"} (none = all)</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, fontSize: 13 }}>
                    {all.length === 0 && <span className="text-[var(--on-variant)]">All</span>}
                    {all.map(v => (
                      <label key={v} style={{ display: "flex", gap: 4, alignItems: "center" }}>
                        <input type="checkbox" checked={form[k].includes(v)} disabled={!canEdit}
                               onChange={e => toggleList(k, v, e.target.checked)} />{v}
                      </label>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {canEdit && (
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          <button className="btn btn-outline" onClick={() => save("close")} disabled={saving || Object.keys(errors).length > 0}>
            <i className="ti ti-device-floppy" /> Save &amp; Close
          </button>
          <button className="btn btn-filled" onClick={() => save("continue")} disabled={saving || Object.keys(errors).length > 0}>
            {saving ? "Saving…" : <>Save &amp; Continue <i className="ti ti-arrow-right" /></>}
          </button>
        </div>
      )}
    </div>
  );
}
