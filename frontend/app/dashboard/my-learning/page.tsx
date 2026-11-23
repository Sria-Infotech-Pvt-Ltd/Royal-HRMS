"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { useFetch } from "@/hooks/useFetch";
import { STATUS_BADGE, STATUS_LABEL, formatDate, type MyTraining, type TrainingStatus } from "@/lib/training";

const FILTERS: { key: "" | TrainingStatus; label: string }[] = [
  { key: "", label: "All" }, { key: "assigned", label: "Not started" }, { key: "in_progress", label: "In progress" },
  { key: "overdue", label: "Overdue" }, { key: "completed", label: "Completed" }, { key: "failed", label: "Failed" },
];

export default function MyLearningPage() {
  const router = useRouter();
  const { data, loading, error } = useFetch<MyTraining[]>(API.training.my);
  const [filter, setFilter] = useState<"" | TrainingStatus>("");
  const rows = (data ?? []).filter(r => !filter || r.status === filter);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My Learning</div>
          <div className="page-sub">Training assigned to you. Open a course to watch, read and take its assessment.</div>
        </div>
      </div>
      <div className="tabs">
        {FILTERS.map(f => (
          <button key={f.key} className={`tab${filter === f.key ? " active" : ""}`} onClick={() => setFilter(f.key)}>{f.label}</button>
        ))}
      </div>
      {loading && <div className="text-[13px] text-[var(--on-variant)] py-6">Loading…</div>}
      {error && <div className="alert alert-error">{error}</div>}
      {!loading && !error && rows.length === 0 && (
        <div className="card card-body text-[13px] text-[var(--on-variant)] text-center py-10" data-testid="my-learning-empty">
          {filter ? "Nothing here." : "No training has been assigned to you yet."}
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
        {rows.map(r => (
          <button key={r.id} className="card card-body" onClick={() => router.push(`/dashboard/my-learning/${r.id}`)}
                  style={{ textAlign: "left", cursor: "pointer", padding: 0, overflow: "hidden" }}>
            <div style={{ height: 110, background: "var(--bg-low)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              {r.course.has_thumbnail
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={`${API_BASE}${API.training.thumbnailFile(r.course.id)}`} alt=""
                       style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <i className="ti ti-school" style={{ fontSize: 34, color: "var(--primary)" }} />}
            </div>
            <div style={{ padding: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: "var(--on-bg)" }}>{r.course.title}</div>
                <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
              </div>
              <div className="text-[12px] text-[var(--on-variant)] mt-1">
                {[r.course.is_mandatory ? "Mandatory" : "", `${r.material_count} item(s)`,
                  r.course.assessment ? "Assessment" : "", r.due_date ? `Due ${r.due_date}` : "",
                  r.starts_on ? `Starts ${formatDate(r.starts_on)}` : ""].filter(Boolean).join(" · ")}
              </div>
              <div style={{ height: 6, background: "var(--bg-low)", borderRadius: 4, marginTop: 10 }}
                   role="progressbar" aria-valuenow={r.progress_percent} aria-valuemin={0} aria-valuemax={100}>
                <div style={{ width: `${r.progress_percent}%`, height: "100%", borderRadius: 4, background: "var(--primary)" }} />
              </div>
              <div className="text-[11px] text-[var(--on-variant)] mt-1">{r.progress_percent}% of required materials</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
