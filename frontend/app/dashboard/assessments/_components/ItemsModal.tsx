"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { Assessment, AssessmentItem } from "../page";

// ── Item form state ───────────────────────────────────────────────────────────

interface ItemForm {
  item_type: "video" | "quiz";
  title: string; order: string;
  video_url: string; duration_secs: string;
  question: string; option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string; pass_score: string;
}

const EMPTY_ITEM: ItemForm = {
  item_type: "video", title: "", order: "1",
  video_url: "", duration_secs: "",
  question: "", option_a: "", option_b: "", option_c: "", option_d: "",
  correct_option: "a", pass_score: "0",
};

function toItemPayload(f: ItemForm) {
  const base = { item_type: f.item_type, title: f.title.trim(), order: Number(f.order) || 1 };
  if (f.item_type === "video") return { ...base, video_url: f.video_url.trim(), duration_secs: f.duration_secs ? Number(f.duration_secs) : null };
  return { ...base, question: f.question.trim(), option_a: f.option_a.trim(), option_b: f.option_b.trim(), option_c: f.option_c.trim(), option_d: f.option_d.trim(), correct_option: f.correct_option, pass_score: Number(f.pass_score) || 0 };
}

function apiErr(e: unknown) {
  return (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Action failed.";
}

// ── ItemsModal ────────────────────────────────────────────────────────────────

interface Props {
  assessment: Assessment;
  onClose: () => void;
}

export default function ItemsModal({ assessment, onClose }: Props) {
  const { data, loading, refetch } = useFetch<AssessmentItem[]>(API.assessments.items(assessment.id));
  const items = Array.isArray(data) ? data : [];

  const [form,       setForm]       = useState<ItemForm>(EMPTY_ITEM);
  const [editTarget, setEditTarget] = useState<AssessmentItem | null>(null);
  const [showForm,   setShowForm]   = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [formErr,    setFormErr]    = useState("");

  function openAdd() {
    const nextOrder = items.length > 0 ? Math.max(...items.map(i => i.order)) + 1 : 1;
    setForm({ ...EMPTY_ITEM, order: String(nextOrder) });
    setEditTarget(null); setFormErr(""); setShowForm(true);
  }

  function openEdit(item: AssessmentItem) {
    setForm({
      item_type: item.item_type, title: item.title, order: String(item.order),
      video_url: item.video_url ?? "", duration_secs: item.duration_secs != null ? String(item.duration_secs) : "",
      question: item.question ?? "", option_a: item.option_a ?? "", option_b: item.option_b ?? "",
      option_c: item.option_c ?? "", option_d: item.option_d ?? "",
      correct_option: item.correct_option || "a", pass_score: String(item.pass_score ?? 0),
    });
    setEditTarget(item); setFormErr(""); setShowForm(true);
  }

  async function saveItem() {
    if (!form.title.trim()) { setFormErr("Title is required."); return; }
    if (form.item_type === "video" && !form.video_url.trim()) { setFormErr("Video URL is required."); return; }
    if (form.item_type === "quiz" && !form.question.trim()) { setFormErr("Question is required."); return; }
    if (form.item_type === "quiz" && (!form.option_a.trim() || !form.option_b.trim())) { setFormErr("At least options A and B are required."); return; }
    setSaving(true); setFormErr("");
    try {
      editTarget
        ? await clientApi.put(API.assessments.itemDetail(editTarget.id), toItemPayload(form))
        : await clientApi.post(API.assessments.items(assessment.id), toItemPayload(form));
      refetch(); setShowForm(false);
    } catch (e) { setFormErr(apiErr(e)); }
    finally { setSaving(false); }
  }

  async function deleteItem(id: string) {
    if (!confirm("Remove this item?")) return;
    try { await clientApi.delete(API.assessments.itemDetail(id)); refetch(); }
    catch (e) { alert(apiErr(e)); }
  }

  function set(k: keyof ItemForm, v: string) { setForm(p => ({ ...p, [k]: v })); }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 700 }}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-list-details mr-6" /> Items — {assessment.title}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {/* ── Items list ── */}
          {loading ? (
            <div className="text-center py-12"><i className="ti ti-loader-2 spin" /></div>
          ) : items.length === 0 && !showForm ? (
            <div className="text-center py-10 text-[var(--on-variant)] text-sm">No items yet. Add a video or quiz below.</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
              {[...items].sort((a, b) => a.order - b.order).map(item => (
                <div key={item.id} className="settings-card" style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 12 }}>
                  <div className="shrink-0" style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: item.item_type === "video" ? "rgba(30,78,140,0.10)" : "rgba(116,55,200,0.10)", color: item.item_type === "video" ? "var(--primary)" : "#7437c8", fontSize: 14 }}>
                    <i className={`ti ${item.item_type === "video" ? "ti-player-play" : "ti-help-circle"}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{item.order}. {item.title}</div>
                    <div className="text-xs text-[var(--on-variant)]" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                      {item.item_type === "video"
                        ? <span>{item.duration_secs ? `${Math.ceil(item.duration_secs / 60)} min` : "Video"}</span>
                        : <><span>Quiz · {item.pass_score} pts</span>{item.correct_option && <span>Correct: {item.correct_option.toUpperCase()}</span>}</>}
                      {item.created_at && (
                        <span style={{ marginLeft: "auto" }}>
                          {new Date(item.created_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-6 shrink-0">
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(item)}><i className="ti ti-edit" /></button>
                    <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => deleteItem(item.id)}><i className="ti ti-trash" /></button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── Item form ── */}
          {showForm && (
            <div className="settings-card" style={{ padding: 16 }}>
              <div className="settings-card-title mb-12">{editTarget ? "Edit Item" : "Add Item"}</div>
              {formErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{formErr}</div></div>}

              <div className="form-row cols-2 mb-12">
                <div className="field-group">
                  <label className="field-label">Type *</label>
                  <select className="field-input field-select" value={form.item_type} onChange={e => set("item_type", e.target.value as "video" | "quiz")}>
                    <option value="video">Video</option>
                    <option value="quiz">Quiz</option>
                  </select>
                </div>
                <div className="field-group">
                  <label className="field-label">Order</label>
                  <input type="number" className="field-input" value={form.order} onChange={e => set("order", e.target.value)} min={1} />
                </div>
              </div>

              <div className="field-group mb-12">
                <label className="field-label">Title *</label>
                <input className="field-input" value={form.title} onChange={e => set("title", e.target.value)} placeholder={form.item_type === "video" ? "e.g. Company Introduction" : "e.g. Policy Quiz Q1"} />
              </div>

              {form.item_type === "video" && (
                <div className="form-row cols-2 mb-12">
                  <div className="field-group">
                    <label className="field-label">Video URL *</label>
                    <input className="field-input" value={form.video_url} onChange={e => set("video_url", e.target.value)} placeholder="https://youtu.be/..." />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Duration (seconds)</label>
                    <input type="number" className="field-input" value={form.duration_secs} onChange={e => set("duration_secs", e.target.value)} placeholder="180" min={0} />
                  </div>
                </div>
              )}

              {form.item_type === "quiz" && (
                <>
                  <div className="field-group mb-12">
                    <label className="field-label">Question *</label>
                    <input className="field-input" value={form.question} onChange={e => set("question", e.target.value)} placeholder="e.g. What is the notice period?" />
                  </div>
                  <div className="form-row cols-2 mb-12">
                    {(["a", "b", "c", "d"] as const).map(opt => (
                      <div key={opt} className="field-group">
                        <label className="field-label">Option {opt.toUpperCase()}{opt === "a" || opt === "b" ? " *" : ""}</label>
                        <input className="field-input" value={form[`option_${opt}` as keyof ItemForm]} onChange={e => set(`option_${opt}` as keyof ItemForm, e.target.value)} placeholder={`Option ${opt.toUpperCase()}`} />
                      </div>
                    ))}
                  </div>
                  <div className="form-row cols-2 mb-12">
                    <div className="field-group">
                      <label className="field-label">Correct Option *</label>
                      <select className="field-input field-select" value={form.correct_option} onChange={e => set("correct_option", e.target.value)}>
                        {["a", "b", "c", "d"].map(o => <option key={o} value={o}>Option {o.toUpperCase()}</option>)}
                      </select>
                    </div>
                    <div className="field-group">
                      <label className="field-label">Points (pass score)</label>
                      <input type="number" className="field-input" value={form.pass_score} onChange={e => set("pass_score", e.target.value)} min={0} />
                    </div>
                  </div>
                </>
              )}

              <div className="flex gap-8 justify-end">
                <button className="btn btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={saveItem} disabled={saving}>
                  {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : editTarget ? "Update Item" : "Add Item"}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          {!showForm && (
            <button className="btn btn-secondary" onClick={openAdd}>
              <i className="ti ti-plus" /> Add Item
            </button>
          )}
          <button className="btn btn-ghost" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}
