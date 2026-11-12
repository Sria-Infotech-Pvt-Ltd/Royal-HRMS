"use client";

import { use, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import {
  MATERIAL_ICON, STATUS_BADGE, STATUS_LABEL, formatDate, materialHint, materialKindLabel, type MyTraining,
} from "@/lib/training";
import MaterialViewer from "../_components/MaterialViewer";
import AssessmentPanel from "../_components/AssessmentPanel";

export default function MyCoursePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { data, loading, error, refetch } = useFetch<MyTraining>(API.training.myDetail(id));
  const [selected, setSelected] = useState<string | null>(null);
  const [showAssessment, setShowAssessment] = useState(false);

  const materials = useMemo(() => data?.materials ?? [], [data]);
  // Default to the first material not yet completed.
  useEffect(() => {
    if (!selected && materials.length) {
      setSelected((materials.find(m => !m.progress?.completed_at) ?? materials[0]).id);
    }
  }, [materials, selected]);

  if (loading && !data) return <div className="text-[13px] text-[var(--on-variant)] py-10">Loading…</div>;
  if (error || !data) return <div className="alert alert-error">{error ?? "Training not found."}</div>;

  const current = materials.find(m => m.id === selected) ?? null;
  const closed = data.status === "failed";
  const a = data.assessment;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">{data.course.title}</div>
          <div className="page-sub">
            {[data.course.category, data.due_date ? `Due ${data.due_date}` : "", `${data.progress_percent}% complete`]
              .filter(Boolean).join(" · ")}
          </div>
        </div>
        <div className="page-actions">
          <span className={STATUS_BADGE[data.status]}>{STATUS_LABEL[data.status]}</span>
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/my-learning")}>
            <i className="ti ti-arrow-left" /> My Learning
          </button>
        </div>
      </div>

      {data.course.description && <div className="card card-body text-[13px] mb-16">{data.course.description}</div>}
      {closed && (
        <div className="alert alert-error mb-16">
          You have used all assessment attempts without passing. HR can reset your attempts.
        </div>
      )}
      {data.starts_on && (
        <div className="alert alert-info mb-16" data-testid="course-not-open">
          <i className="ti ti-calendar" /> This course starts on {formatDate(data.starts_on)}. The materials and the
          assessment open on that date.
        </div>
      )}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "flex-start" }}>
        <div className="card card-body" style={{ padding: 10, flex: "1 1 240px", maxWidth: 340 }}>
          {materials.map((m, i) => {
            const done = !!m.progress?.completed_at;
            return (
              <button key={m.id} onClick={() => { setSelected(m.id); setShowAssessment(false); }}
                      style={{ display: "flex", gap: 10, width: "100%", textAlign: "left", padding: 10, borderRadius: 8,
                               background: !showAssessment && selected === m.id ? "var(--bg-low)" : "transparent" }}>
                <i className={`ti ${done ? "ti-circle-check" : MATERIAL_ICON[m.material_type]}`}
                   style={{ fontSize: 18, color: done ? "#16a34a" : "var(--primary)" }} />
                <span style={{ flex: 1 }}>
                  <span style={{ display: "block", fontSize: 13, fontWeight: 600 }}>{i + 1}. {m.title}</span>
                  <span className="text-[11px] text-[var(--on-variant)]">
                    {materialKindLabel(m)}{m.is_required ? "" : " · optional"} · {materialHint(m)}
                  </span>
                </span>
              </button>
            );
          })}
          {a?.required && (
            <button onClick={() => setShowAssessment(true)}
                    style={{ display: "flex", gap: 10, width: "100%", textAlign: "left", padding: 10, borderRadius: 8,
                             background: showAssessment ? "var(--bg-low)" : "transparent" }}>
              <i className={`ti ${a.passed ? "ti-circle-check" : a.unlocked ? "ti-clipboard-check" : "ti-lock"}`}
                 style={{ fontSize: 18, color: a.passed ? "#16a34a" : "var(--primary)" }} />
              <span>
                <span style={{ display: "block", fontSize: 13, fontWeight: 600 }}>Assessment</span>
                <span className="text-[11px] text-[var(--on-variant)]">
                  {a.passed ? `Passed (${a.best_score_percent}%)` : a.unlocked ? "Available" : "Complete the materials first"}
                </span>
              </span>
            </button>
          )}
          {materials.length === 0 && <div className="text-[13px] text-[var(--on-variant)] p-2">No materials yet.</div>}
        </div>

        <div style={{ flex: "3 1 420px", minWidth: 0 }}>
          {data.starts_on ? null : showAssessment && a?.required
            ? <AssessmentPanel assignmentId={data.id} state={a} onDone={refetch} />
            : current && <MaterialViewer key={current.id} assignmentId={data.id} material={current}
                                         disabled={closed} onProgress={refetch} />}
        </div>
      </div>
    </div>
  );
}
