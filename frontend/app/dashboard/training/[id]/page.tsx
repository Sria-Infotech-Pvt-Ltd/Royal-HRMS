"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import {
  apiError, type AssignmentRow, type Course,
} from "@/lib/training";
import { ProgressTable } from "../_components/TrainingTables";
import CourseDetailsForm from "../_components/CourseDetailsForm";
import MaterialsEditor from "../_components/MaterialsEditor";
import AssignPanel from "../_components/AssignPanel";

type Tab = "details" | "materials" | "assign" | "progress";

export default function CourseEditorPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const canEdit = usePermission("training.edit");
  const canDelete = usePermission("training.delete");
  const canAssign = usePermission("training.assign");
  const canReset = usePermission("training.manage_assessments");
  const [tab, setTab] = useState<Tab>("details");
  const { showToast } = useToast();

  const { data: course, loading, error, refetch } = useFetch<Course>(API.training.course(id));
  const { data: progress, refetch: refetchProgress } = useFetch<AssignmentRow[]>(
    tab === "progress" ? API.training.progress(id) : null);

  async function remove() {
    if (!course || !window.confirm(`Delete "${course.title}"? Courses with training history are archived instead.`)) return;
    try {
      const res = await clientApi.delete<{ message: string }>(API.training.course(id));
      showToast(res.data.message, "success");
      router.push("/dashboard/training");
    } catch (e) {
      showToast(apiError(e, "Failed to delete the course."), "error");
    }
  }

  async function rowAction(r: AssignmentRow, action: "reset" | "remove") {
    const q = action === "reset"
      ? `Give ${r.employee.name} a fresh set of assessment attempts?`
      : `Remove this course from ${r.employee.name}?`;
    if (!window.confirm(q)) return;
    try {
      if (action === "reset") await clientApi.post(API.training.resetAssessment(r.id));
      else await clientApi.delete(API.training.assignment(r.id));
      showToast(action === "reset" ? "Assessment attempts reset." : "Assignment removed.", "success");
      refetchProgress();
    } catch (e) {
      showToast(apiError(e, "Action failed."), "error");
    }
  }

  if (loading && !course) return <div className="text-[13px] text-[var(--on-variant)] py-10">Loading course…</div>;
  if (error || !course) return <div className="alert alert-error">{error ?? "Course not found."}</div>;

  const tabs: { key: Tab; label: string; icon: string; show: boolean }[] = [
    { key: "details", label: "Details", icon: "ti-info-circle", show: true },
    { key: "materials", label: `Materials (${course.materials?.length ?? 0})`, icon: "ti-files", show: true },
    { key: "assign", label: "Assign", icon: "ti-user-plus", show: canAssign && !course.archived },
    { key: "progress", label: "Progress", icon: "ti-chart-bar", show: true },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">{course.title}</div>
          <div className="page-sub">
            {[course.category, course.is_mandatory ? "Mandatory" : "Optional",
              course.archived ? "Archived" : course.is_active ? "Active" : "Inactive"].filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/training")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          {canDelete && !course.archived && (
            <button className="btn btn-ghost" onClick={remove}><i className="ti ti-trash" /> Delete</button>
          )}
        </div>
      </div>

      <div className="tabs">
        {tabs.filter(t => t.show).map(t => (
          <button key={t.key} className={`tab${tab === t.key ? " active" : ""}`} onClick={() => setTab(t.key)}>
            <i className={`ti ${t.icon}`} style={{ marginRight: 5 }} />{t.label}
          </button>
        ))}
      </div>

      {tab === "details" && (
        <CourseDetailsForm course={course} canEdit={canEdit && !course.archived} onSaved={refetch}
                           onContinue={() => setTab("materials")} onClose={() => router.push("/dashboard/training")} />
      )}
      {tab === "materials" && (
        <MaterialsEditor course={course} canEdit={canEdit && !course.archived} onChanged={refetch}
                         onContinue={() => setTab(canAssign && !course.archived ? "assign" : "progress")}
                         continueLabel={canAssign && !course.archived ? "Continue to Assign" : "View Progress"}
                         onClose={() => router.push("/dashboard/training")} />
      )}
      {tab === "assign" && (
        <AssignPanel course={course} onDone={() => setTab("progress")} onClose={() => router.push("/dashboard/training")} />
      )}
      {tab === "progress" && (
        <div className="card card-body">
          {!progress && <div className="text-[13px] text-[var(--on-variant)]">Loading…</div>}
          {progress && progress.length === 0 && (
            <div className="text-[13px] text-[var(--on-variant)] py-4">No one in your scope has this course yet.</div>
          )}
          {progress && progress.length > 0 && (
            <ProgressTable rows={progress} actions={r => (
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                {canReset && r.status === "failed" && (
                  <button className="btn btn-ghost" style={{ padding: "3px 8px", fontSize: 12 }}
                          onClick={() => rowAction(r, "reset")}>Reset attempts</button>
                )}
                {canAssign && r.status === "assigned" && !r.started_at && (
                  <button className="btn btn-ghost" style={{ padding: "3px 8px", fontSize: 12 }}
                          onClick={() => rowAction(r, "remove")}>Remove</button>
                )}
              </div>
            )} />
          )}
        </div>
      )}
    </div>
  );
}
