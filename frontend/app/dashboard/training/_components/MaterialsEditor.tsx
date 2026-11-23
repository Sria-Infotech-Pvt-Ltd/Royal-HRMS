"use client";

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import {
  MATERIAL_ICON, apiError, formatBytes, formatDuration, materialKindLabel, needsVideoLength, parseVideoLength,
  parseVideoLink, uploadError, videoLengthSeconds, type Course, type Material, type MaterialType,
} from "@/lib/training";
import MaterialPreview from "./MaterialPreview";

// Client-side pre-checks only; the server enforces its own configurable limits
// (uploads pass through the /api proxy, which forwards at most 10 MB).
const MAX_DOC_MB = 9;
const MAX_VIDEO_MB = 9;

export default function MaterialsEditor({ course, canEdit, onChanged, onContinue, continueLabel, onClose }: {
  course: Course; canEdit: boolean; onChanged: () => void;
  /** Next step (Assign, or Progress for users who can't assign). Materials save as they are added. */
  onContinue?: () => void;
  continueLabel?: string;
  /** Back to the course list. */
  onClose?: () => void;
}) {
  const materials = course.materials ?? [];
  const { showToast } = useToast();
  const [openId, setOpenId] = useState<string | null>(null);
  // The add form starts open only while the course has no materials.
  const [addOpen, setAddOpen] = useState(materials.length === 0);

  async function move(index: number, delta: number) {
    const ids = materials.map(m => m.id);
    const j = index + delta;
    if (j < 0 || j >= ids.length) return;
    [ids[index], ids[j]] = [ids[j], ids[index]];
    try {
      await clientApi.post(API.training.reorder(course.id), { order: ids });
      onChanged();
    } catch (e) {
      showToast(apiError(e, "Failed to reorder."), "error");
    }
  }

  async function patch(m: Material, body: Record<string, unknown>) {
    try {
      await clientApi.patch(API.training.material(m.id), body);
      onChanged();
    } catch (e) {
      showToast(apiError(e, "Failed to save the material."), "error");
    }
  }

  async function setLength(m: Material) {
    const text = window.prompt(`Length of "${m.title}" (minutes:seconds, e.g. 12:30)`);
    if (text == null) return;
    const seconds = parseVideoLength(text);
    if (!seconds) { showToast("Enter the length as minutes:seconds, e.g. 12:30.", "error"); return; }
    await patch(m, { duration_seconds: seconds });
  }

  async function remove(m: Material) {
    if (!window.confirm(`Remove "${m.title}"? Employees' progress history is kept.`)) return;
    try {
      await clientApi.delete(API.training.material(m.id));
      showToast(`"${m.title}" removed.`, "success");
      onChanged();
    } catch (e) {
      showToast(apiError(e, "Failed to remove the material."), "error");
    }
  }

  return (
    <div className="card card-body" data-testid="materials-editor">
      {materials.length === 0 && (
        <div className="text-[13px] text-[var(--on-variant)] py-3">No learning materials yet.</div>
      )}
      {materials.length > 0 && (
        <div className="text-[12px] text-[var(--on-variant)]" style={{ marginBottom: 6 }}>
          Click a material to preview it.
        </div>
      )}
      {materials.map((m, i) => (
        <div key={m.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 0", flexWrap: "wrap" }}>
          <button type="button" onClick={() => setOpenId(openId === m.id ? null : m.id)}
                  aria-expanded={openId === m.id} aria-label={`${openId === m.id ? "Hide" : "Preview"} ${m.title}`}
                  style={{ display: "flex", gap: 12, alignItems: "center", flex: 1, minWidth: 220, textAlign: "left",
                           background: "none", border: 0, padding: 0, cursor: "pointer" }}>
          <i className={`ti ti-chevron-${openId === m.id ? "down" : "right"}`} style={{ fontSize: 16, color: "var(--on-variant)" }} />
          <span className="text-[12px] text-[var(--on-variant)]" style={{ width: 18 }}>{i + 1}.</span>
          <i className={`ti ${MATERIAL_ICON[m.material_type]}`} style={{ fontSize: 20, color: "var(--primary)" }} />
          <div style={{ flex: 1, minWidth: 180 }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{m.title}</div>
            <div className="text-[11px] text-[var(--on-variant)]">
              {[materialKindLabel(m), formatBytes(m.file_size), formatDuration(m.duration_seconds),
                m.material_type === "document" && m.min_view_seconds ? `min. ${formatDuration(m.min_view_seconds)} reading` : "",
                !m.is_tracked && m.material_type !== "document"
                  ? (m.allow_manual_completion ? "completion confirmed by employee" : "not trackable — allow confirmation")
                  : ""].filter(Boolean).join(" · ")}
            </div>
          </div>
          </button>
          {canEdit && (
            <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
              {m.is_tracked && !m.duration_seconds && (
                <button className="btn btn-outline btn-sm" onClick={() => setLength(m)}
                        title="Needed to check how much of the video was watched">
                  <i className="ti ti-alert-triangle" /> Set video length
                </button>
              )}
              {course.videos_optional && m.material_type !== "document" ? (
                <span className="badge badge-neutral" title="Course setting: video watching optional">Optional (course setting)</span>
              ) : (
                <label style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 12 }}
                       title={requiredHint(m.material_type, !!course.assessment)}>
                  <input type="checkbox" checked={m.is_required} onChange={e => patch(m, { is_required: e.target.checked })} />
                  {requiredLabel(m.material_type, !!course.assessment)}
                </label>
              )}
              {m.material_type === "external_video" && !m.is_tracked && (
                <label style={{ display: "flex", gap: 4, alignItems: "center", fontSize: 12 }}>
                  <input type="checkbox" checked={m.allow_manual_completion}
                         onChange={e => patch(m, { allow_manual_completion: e.target.checked })} />
                  Allow confirmation
                </label>
              )}
              <button className="btn btn-ghost" style={{ padding: "2px 8px" }} aria-label="Move up" disabled={i === 0}
                      onClick={() => move(i, -1)}><i className="ti ti-arrow-up" /></button>
              <button className="btn btn-ghost" style={{ padding: "2px 8px" }} aria-label="Move down"
                      disabled={i === materials.length - 1} onClick={() => move(i, 1)}><i className="ti ti-arrow-down" /></button>
              <button className="btn btn-ghost" style={{ padding: "2px 8px" }} aria-label="Remove" onClick={() => remove(m)}>
                <i className="ti ti-trash" />
              </button>
            </div>
          )}
        </div>
        {openId === m.id && (
          <div style={{ padding: "4px 0 16px 46px" }} data-testid="material-preview">
            {m.description && <div className="text-[13px] mb-2">{m.description}</div>}
            <MaterialPreview material={m} />
          </div>
        )}
        </div>
      ))}
      {canEdit && <AddMaterial courseId={course.id} onAdded={onChanged} open={addOpen}
                               onToggle={() => setAddOpen(o => !o)} hasAssessment={!!course.assessment}
                               videosOptional={!!course.videos_optional} />}

      {(onClose || onContinue) && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap",
                      marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--outline-v)" }}>
          <span className="text-[12px] text-[var(--on-variant)]">
            <i className="ti ti-circle-check" style={{ color: "var(--success)" }} /> Materials are saved as soon as they are added.
          </span>
          <div style={{ display: "flex", gap: 10 }}>
            {onClose && (
              <button className="btn btn-outline" onClick={onClose}>
                <i className="ti ti-check" /> Done &amp; Close
              </button>
            )}
            {onContinue && (
              <button className="btn btn-filled" onClick={onContinue} disabled={materials.length === 0}
                      title={materials.length === 0 ? "Add at least one material first" : undefined}>
                {continueLabel ?? "Continue"} <i className="ti ti-arrow-right" />
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** "Required — must be read/watched before the assessment" (or "to complete the course"). */
export function requiredLabel(kind: MaterialType, hasAssessment: boolean): string {
  return `Required — must be ${kind === "document" ? "read" : "watched"} ${hasAssessment ? "before the assessment" : "to complete the course"}`;
}

function requiredHint(kind: MaterialType, hasAssessment: boolean): string {
  return `Unticked: optional — employees can skip this ${kind === "document" ? "document" : "video"}${
    hasAssessment ? " and still take the assessment" : ""}.`;
}

function AddMaterial({ courseId, onAdded, open, onToggle, hasAssessment, videosOptional }: {
  courseId: string; onAdded: () => void; open: boolean; onToggle: () => void;
  hasAssessment: boolean; videosOptional: boolean;
}) {
  const [kind, setKind] = useState<MaterialType>("document");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [link, setLink] = useState("");
  const [minView, setMinView] = useState("");
  const [durMin, setDurMin] = useState("");
  const [durSec, setDurSec] = useState("");
  const [required, setRequired] = useState(true);
  const [allowConfirm, setAllowConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [pct, setPct] = useState(0);
  const [tried, setTried] = useState(false);
  const { showToast } = useToast();

  const parsed = kind === "external_video" && link ? parseVideoLink(link) : null;
  const titleError = title.trim() ? "" : "Give the material a title.";
  const sourceError = kind === "external_video"
    ? (parsed && "error" in parsed ? parsed.error : link.trim() ? "" : "Paste the video link.")
    : uploadError(file, kind === "video" ? "video" : "document", kind === "video" ? MAX_VIDEO_MB : MAX_DOC_MB);
  const lengthSeconds = videoLengthSeconds(durMin, durSec);
  const lengthRequired = needsVideoLength(kind, parsed && !("error" in parsed) ? parsed.provider : null);
  const lengthError = kind === "document" ? ""
    : Number(durSec || 0) > 59 ? "Seconds must be 0–59."
    : lengthRequired && !lengthSeconds ? "Enter the video length." : "";

  async function add() {
    setTried(true);
    if (titleError || sourceError || lengthError) return;
    setBusy(true);
    setPct(0);
    try {
      if (kind === "external_video") {
        await clientApi.post(API.training.materials(courseId), {
          material_type: kind, title: title.trim(), external_url: link.trim(), is_required: required,
          allow_manual_completion: allowConfirm, duration_seconds: lengthSeconds || null,
        });
      } else {
        const fd = new FormData();
        fd.append("material_type", kind);
        fd.append("title", title.trim());
        fd.append("file", file as File);
        fd.append("is_required", String(required));
        if (kind === "document" && minView) fd.append("min_view_seconds", String(Number(minView) * 60));
        if (kind === "video" && lengthSeconds) fd.append("duration_seconds", String(lengthSeconds));
        await clientApi.post(API.training.materials(courseId), fd, {
          timeout: 0,
          onUploadProgress: ev => setPct(ev.total ? Math.round((ev.loaded / ev.total) * 100) : 0),
        });
      }
      showToast(`"${title.trim()}" added.`, "success");
      setTitle(""); setFile(null); setLink(""); setMinView(""); setDurMin(""); setDurSec(""); setRequired(true);
      setAllowConfirm(false); setTried(false);
      onAdded();
    } catch (e) {
      showToast(apiError(e, "Failed to add the material."), "error");
    } finally {
      setBusy(false);
    }
  }

  const untrackedLink = parsed && !("error" in parsed) && parsed.provider === "vimeo";
  const maxMb = kind === "video" ? MAX_VIDEO_MB : MAX_DOC_MB;
  const CONTROL_HEIGHT = 44;
  const hint = (text: string, error?: string) => (
    <div style={{ minHeight: 18, marginTop: 6, fontSize: 12, lineHeight: "18px" }}
         className={error ? "text-red-600" : "text-[var(--on-variant)]"} role={error ? "alert" : undefined}>
      {error || text}
    </div>
  );

  return (
    <div style={{ marginTop: 16, padding: 18, borderRadius: 12, background: "var(--bg-low)",
                  border: "1px solid var(--outline-v)" }} data-testid="add-material">
      <button type="button" onClick={onToggle} aria-expanded={open}
              style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", background: "none", border: 0,
                       padding: 0, cursor: "pointer", fontWeight: 600, fontSize: 14, color: "var(--on-bg)",
                       marginBottom: open ? 12 : 0 }}>
        <i className={`ti ${open ? "ti-chevron-down" : "ti-plus"}`} style={{ color: "var(--primary)", fontSize: 16 }} />
        Add learning material
        {!open && <span className="text-[12px] text-[var(--on-variant)]" style={{ fontWeight: 400 }}>— click to open</span>}
      </button>
      {open && (<>

      <div role="radiogroup" aria-label="Material type" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {([["document", "ti-file-text", "Document", "PDF, PPTX, DOCX"],
           ["video", "ti-video", "Upload video", "MP4, WebM"],
           ["external_video", "ti-link", "Video link", "YouTube, Vimeo, .mp4"]] as [MaterialType, string, string, string][])
          .map(([k, icon, label, sub]) => {
            const on = kind === k;
            return (
              <button key={k} type="button" role="radio" aria-checked={on}
                      onClick={() => { setKind(k); setFile(null); setTried(false); }}
                      style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 14px", borderRadius: 8,
                               cursor: "pointer", background: on ? "#fff" : "transparent",
                               border: `1.5px solid ${on ? "var(--primary)" : "var(--outline-v)"}` }}>
                <i className={`ti ${icon}`} style={{ fontSize: 17, color: on ? "var(--primary)" : "var(--on-variant)" }} />
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{label}</span>
                <span className="text-[11px] text-[var(--on-variant)]">{sub}</span>
              </button>
            );
          })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16,
                    alignItems: "start" }}>
        <div>
          <label className="field-label" htmlFor="am-title">Title *</label>
          <input id="am-title" className="field-input" style={{ height: CONTROL_HEIGHT }} value={title} maxLength={200}
                 placeholder="e.g. Fire safety basics" onChange={e => setTitle(e.target.value)} />
          {hint("Shown to employees in the course", tried ? titleError : "")}
        </div>

        {kind === "external_video" ? (
          <div>
            <label className="field-label" htmlFor="am-link">Video link *</label>
            <input key="link" id="am-link" className="field-input" style={{ height: CONTROL_HEIGHT }} value={link}
                   placeholder="https://www.youtube.com/watch?v=…" onChange={e => setLink(e.target.value)} />
            {hint("Public YouTube, Vimeo or https .mp4 / .webm link", tried ? sourceError : "")}
          </div>
        ) : (
          <div>
            <label className="field-label" htmlFor="am-file">File *</label>
            {/* Own key per type: the file chosen for the other type is cleared. */}
            <input key={`file-${kind}`} id="am-file" type="file" hidden
                   accept={kind === "video" ? ".mp4,.webm,.m4v,video/mp4,video/webm" : ".pdf,.pptx,.docx"}
                   onChange={e => setFile(e.target.files?.[0] ?? null)} />
            <label htmlFor="am-file" className="field-input"
                   style={{ height: CONTROL_HEIGHT, display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
                            padding: "0 8px 0 6px", background: "#fff" }}>
              <span className="btn btn-outline btn-sm" style={{ pointerEvents: "none", flexShrink: 0 }}>
                <i className="ti ti-upload" /> Choose file
              </span>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13,
                             color: file ? "var(--on-bg)" : "var(--on-variant)" }}>
                {file ? file.name : "No file chosen"}
              </span>
            </label>
            {hint(kind === "video" ? `Max ${maxMb} MB · longer videos: use a Video link` : `Max ${maxMb} MB`,
                  tried ? sourceError : "")}
          </div>
        )}

        {kind === "document" ? (
          <div>
            <label className="field-label" htmlFor="am-min">Minimum reading time</label>
            <input id="am-min" className="field-input" style={{ height: CONTROL_HEIGHT }} inputMode="numeric"
                   placeholder="Minutes (optional)" value={minView}
                   onChange={e => setMinView(e.target.value.replace(/\D/g, ""))} />
            {hint("Employees can confirm reading after this time")}
          </div>
        ) : (
          <div>
            <label className="field-label" htmlFor="am-dur">Video length{lengthRequired ? " *" : ""}</label>
            <div style={{ display: "flex", gap: 8 }}>
              <input id="am-dur" className="field-input" style={{ height: CONTROL_HEIGHT }} inputMode="numeric"
                     placeholder="Minutes" aria-label="Video length minutes" value={durMin} maxLength={4}
                     onChange={e => setDurMin(e.target.value.replace(/\D/g, ""))} />
              <input id="am-dur-sec" className="field-input" style={{ height: CONTROL_HEIGHT }} inputMode="numeric"
                     placeholder="Seconds" aria-label="Video length seconds" value={durSec} maxLength={2}
                     onChange={e => setDurSec(e.target.value.replace(/\D/g, ""))} />
            </div>
            {hint(lengthRequired ? "Required — used to check how much was watched" : "Optional for Vimeo links",
                  tried || Number(durSec || 0) > 59 ? lengthError : "")}
          </div>
        )}
      </div>

      {kind !== "document" && videosOptional ? (
        <div className="text-[12px] text-[var(--on-variant)]" style={{ marginTop: 4 }}>
          <i className="ti ti-info-circle" /> Video watching is optional for this course (course setting).
        </div>
      ) : (
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, marginTop: 4 }}
               title={requiredHint(kind, hasAssessment)}>
          <input type="checkbox" checked={required} onChange={e => setRequired(e.target.checked)} />
          {requiredLabel(kind, hasAssessment)}
        </label>
      )}

      {untrackedLink && (
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, marginTop: 4 }}>
          <input type="checkbox" checked={allowConfirm} onChange={e => setAllowConfirm(e.target.checked)} />
          Vimeo playback can&apos;t be tracked — let employees confirm they watched it
        </label>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 14,
                    paddingTop: 14, borderTop: "1px solid var(--outline-v)" }}>
        {busy && kind !== "external_video" && (
          <span className="text-[12px] text-[var(--on-variant)]">Uploading… {pct}%</span>
        )}
        <button className="btn btn-filled" onClick={add} disabled={busy}>
          <i className="ti ti-plus" /> {busy ? "Saving…" : "Add Material"}
        </button>
      </div>
      </>)}
    </div>
  );
}
