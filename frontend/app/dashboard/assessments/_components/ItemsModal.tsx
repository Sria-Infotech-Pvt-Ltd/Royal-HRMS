"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { Assessment, AssessmentItem, AssessmentSection } from "../page";

// ── Types ─────────────────────────────────────────────────────────────────────

interface SectionForm { title: string; order: string; score: string; }
interface ItemForm {
  item_type: "video" | "quiz"; title: string; order: string;
  video_url: string; duration_secs: string;
  question: string; option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string;
}

const EMPTY_SECTION: SectionForm = { title: "", order: "1", score: "0" };
const EMPTY_ITEM: ItemForm = {
  item_type: "quiz", title: "", order: "1",
  video_url: "", duration_secs: "",
  question: "", option_a: "", option_b: "", option_c: "", option_d: "",
  correct_option: "a",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function toEmbedUrl(url: string): string | null {
  if (!url) return null;
  const yt1 = url.match(/youtu\.be\/([^?&/]+)/);   if (yt1) return `https://www.youtube.com/embed/${yt1[1]}`;
  const yt2 = url.match(/[?&]v=([^?&]+)/);         if (yt2) return `https://www.youtube.com/embed/${yt2[1]}`;
  const vim = url.match(/vimeo\.com\/(\d+)/);       if (vim) return `https://player.vimeo.com/video/${vim[1]}`;
  return null;
}

function VideoLink({ url }: { url: string }) {
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
      style={{ fontSize: ".75rem", color: "var(--primary)", display: "inline-flex", alignItems: "center", gap: 4, textDecoration: "none", marginTop: 2 }}>
      <i className="ti ti-external-link" style={{ fontSize: 11 }} />
      {toEmbedUrl(url) ? "Watch video" : url.length > 48 ? url.slice(0, 48) + "…" : url}
    </a>
  );
}

function VideoPreview({ url }: { url: string }) {
  if (!url) return null;
  const embed = toEmbedUrl(url);
  if (embed) return (
    <div style={{ borderRadius: 10, overflow: "hidden", aspectRatio: "16/9", marginTop: 8, background: "#000" }}>
      <iframe src={embed} allow="autoplay; fullscreen" allowFullScreen style={{ width: "100%", height: "100%", border: "none", display: "block" }} />
    </div>
  );
  return (
    <div style={{ marginTop: 8, borderRadius: 10, overflow: "hidden", background: "#000" }}>
      <video src={url} controls style={{ width: "100%", display: "block", maxHeight: 220 }} />
    </div>
  );
}

function apiErr(e: unknown) {
  return (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Action failed.";
}

// ── Component ─────────────────────────────────────────────────────────────────

interface Props { assessment: Assessment; onClose: () => void; }

export default function ItemsModal({ assessment, onClose }: Props) {
  const { data: fetchedSections, loading: sectionsLoading, refetch: refetchSections } =
    useFetch<AssessmentSection[]>(API.assessments.sections(assessment.id));
  const { data: fetchedItems, loading: itemsLoading, refetch: refetchItems } =
    useFetch<AssessmentItem[]>(API.assessments.items(assessment.id));

  const sections: AssessmentSection[] = Array.isArray(fetchedSections) ? [...fetchedSections].sort((a, b) => a.order - b.order) : [];
  const items: AssessmentItem[]       = Array.isArray(fetchedItems)   ? fetchedItems   : (assessment.items ?? []);

  const loading = sectionsLoading || itemsLoading;

  // ── Panel state ──
  const [panelMode,       setPanelMode]       = useState<"section" | "item" | null>(null);
  const [sectionForm,     setSectionForm]     = useState<SectionForm>(EMPTY_SECTION);
  const [editSectionId,   setEditSectionId]   = useState<string | null>(null);
  const [itemForm,        setItemForm]        = useState<ItemForm>(EMPTY_ITEM);
  const [editItemId,      setEditItemId]      = useState<string | null>(null);
  const [forSectionId,    setForSectionId]    = useState<string | null>(null);
  const [questionType,    setQuestionType]    = useState<"mcq" | "truefalse">("mcq");
  const [saving,          setSaving]          = useState(false);
  const [formErr,         setFormErr]         = useState("");

  function closePanel() { setPanelMode(null); setEditSectionId(null); setEditItemId(null); setFormErr(""); }

  // ── Section helpers ──
  function openAddSection() {
    setSectionForm({ ...EMPTY_SECTION, order: String(sections.length + 1) });
    setEditSectionId(null); setFormErr(""); setPanelMode("section");
  }
  function openEditSection(s: AssessmentSection) {
    setSectionForm({ title: s.title, order: String(s.order), score: String(s.score) });
    setEditSectionId(s.id); setFormErr(""); setPanelMode("section");
  }
  async function saveSection() {
    if (!sectionForm.title.trim()) { setFormErr("Title is required."); return; }
    setSaving(true); setFormErr("");
    const payload = { title: sectionForm.title.trim(), order: Number(sectionForm.order) || 1, score: Number(sectionForm.score) || 0 };
    try {
      editSectionId
        ? await clientApi.put(API.assessments.sectionDetail(assessment.id, editSectionId), payload)
        : await clientApi.post(API.assessments.sections(assessment.id), payload);
      refetchSections(); closePanel();
    } catch (e) { setFormErr(apiErr(e)); }
    finally { setSaving(false); }
  }
  async function deleteSection(id: string) {
    if (!confirm("Delete this section? Items will become unsectioned.")) return;
    setFormErr("");
    try { await clientApi.delete(API.assessments.sectionDetail(assessment.id, id)); refetchSections(); refetchItems(); }
    catch (e) { setFormErr(apiErr(e)); }
  }

  // ── Item helpers ──
  function openAddItem(sectionId: string | null) {
    const nextOrder = items.length > 0 ? Math.max(...items.map(i => i.order)) + 1 : 1;
    setItemForm({ ...EMPTY_ITEM, order: String(nextOrder) });
    setEditItemId(null); setForSectionId(sectionId);
    setFormErr(""); setQuestionType("mcq"); setPanelMode("item");
  }
  function openEditItem(item: AssessmentItem) {
    setItemForm({
      item_type: item.item_type, title: item.title, order: String(item.order),
      video_url: item.video_url ?? "", duration_secs: item.duration_secs != null ? String(item.duration_secs) : "",
      question: item.question ?? "", option_a: item.option_a ?? "", option_b: item.option_b ?? "",
      option_c: item.option_c ?? "", option_d: item.option_d ?? "", correct_option: item.correct_option || "a",
    });
    const isTF = item.item_type === "quiz" && item.option_a?.toLowerCase() === "true" && item.option_b?.toLowerCase() === "false" && !item.option_c;
    setEditItemId(item.id); setForSectionId(item.section_id ?? item.section);
    setQuestionType(isTF ? "truefalse" : "mcq"); setFormErr(""); setPanelMode("item");
  }
  function changeQuestionType(qt: "mcq" | "truefalse") {
    setQuestionType(qt);
    if (qt === "truefalse")
      setItemForm(p => ({ ...p, option_a: "True", option_b: "False", option_c: "", option_d: "", correct_option: p.correct_option === "c" || p.correct_option === "d" ? "a" : p.correct_option }));
  }
  async function saveItem() {
    if (!itemForm.title.trim())                                                     { setFormErr("Title is required."); return; }
    if (itemForm.item_type === "video" && !itemForm.video_url.trim())               { setFormErr("Video URL is required."); return; }
    if (itemForm.item_type === "quiz"  && !itemForm.question.trim())                { setFormErr("Question is required."); return; }
    if (itemForm.item_type === "quiz"  && (!itemForm.option_a.trim() || !itemForm.option_b.trim())) { setFormErr("Options A and B are required."); return; }

    const base = { item_type: itemForm.item_type, title: itemForm.title.trim(), order: Number(itemForm.order) || 1, section: forSectionId };
    const payload = itemForm.item_type === "video"
      ? { ...base, video_url: itemForm.video_url.trim(), duration_secs: itemForm.duration_secs ? Number(itemForm.duration_secs) : null }
      : { ...base, question: itemForm.question.trim(), option_a: itemForm.option_a.trim(), option_b: itemForm.option_b.trim(), option_c: itemForm.option_c.trim(), option_d: itemForm.option_d.trim(), correct_option: itemForm.correct_option };

    setSaving(true); setFormErr("");
    try {
      editItemId
        ? await clientApi.put(API.assessments.itemDetail(editItemId), payload)
        : await clientApi.post(API.assessments.items(assessment.id), payload);
      refetchItems(); closePanel();
    } catch (e) { setFormErr(apiErr(e)); }
    finally { setSaving(false); }
  }
  async function deleteItem(id: string) {
    if (!confirm("Remove this item?")) return;
    setFormErr("");
    try { await clientApi.delete(API.assessments.itemDetail(id)); refetchItems(); }
    catch (e) { setFormErr(apiErr(e)); }
  }

  function sectionItems(sectionId: string) {
    return items.filter(i => (i.section_id ?? i.section) === sectionId).sort((a, b) => a.order - b.order);
  }
  const unsectioned = items.filter(i => !(i.section_id ?? i.section)).sort((a, b) => a.order - b.order);

  function setItem(k: keyof ItemForm, v: string) { setItemForm(p => ({ ...p, [k]: v })); }

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 700 }}>
        <div className="modal-header">
          <div className="modal-title"><i className="ti ti-layout-list mr-6" /> Sections — {assessment.title}</div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
          {loading && <div className="text-center py-12"><i className="ti ti-loader-2 spin" /></div>}

          {!loading && sections.length === 0 && items.length === 0 && !panelMode && (
            <div className="text-center py-10" style={{ color: "var(--text-secondary)", fontSize: ".88rem" }}>
              No sections or items yet. Click <strong>Add Section</strong> to get started.
            </div>
          )}

          {!loading && !panelMode && formErr && (
            <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{formErr}</div></div>
          )}

          {!loading && (
            <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 16 }}>

              {sections.map((section, si) => {
                const sItems = sectionItems(section.id);
                return (
                  <div key={section.id} className="settings-card" style={{ padding: 0, overflow: "hidden" }}>
                    {/* Section header */}
                    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: "rgba(30,78,140,0.05)", borderBottom: "1px solid var(--border)" }}>
                      <div style={{ width: 28, height: 28, borderRadius: 8, background: "rgba(30,78,140,0.12)", color: "var(--primary)", fontSize: 13, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontWeight: 700 }}>
                        {si + 1}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontWeight: 600, fontSize: ".88rem" }}>{section.title}</div>
                        <div style={{ fontSize: ".75rem", color: "var(--text-secondary)" }}>
                          {section.score} marks · {section.item_count ?? sItems.length} item{(section.item_count ?? sItems.length) !== 1 ? "s" : ""}
                        </div>
                      </div>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        <button className="btn btn-ghost btn-sm" title="Edit section" onClick={() => openEditSection(section)}><i className="ti ti-edit" /></button>
                        <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} title="Delete section" onClick={() => deleteSection(section.id)}><i className="ti ti-trash" /></button>
                      </div>
                    </div>

                    {/* Items */}
                    {sItems.map((item, ii) => (
                      <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 14px 8px 44px", borderBottom: "1px solid var(--border)" }}>
                        <div style={{ width: 22, height: 22, borderRadius: 6, background: item.item_type === "video" ? "rgba(30,78,140,0.10)" : "rgba(116,55,200,0.10)", color: item.item_type === "video" ? "var(--primary)" : "#7437c8", fontSize: 11, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          <i className={`ti ${item.item_type === "video" ? "ti-player-play" : "ti-help-circle"}`} />
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: ".84rem", fontWeight: 500 }}>{ii + 1}. {item.title}</div>
                          <div style={{ fontSize: ".75rem", color: "var(--text-secondary)" }}>
                            {item.item_type === "video"
                              ? (item.duration_secs ? `${Math.ceil(item.duration_secs / 60)} min` : "Video")
                              : `${item.question?.slice(0, 60) ?? "—"}${(item.question?.length ?? 0) > 60 ? "…" : ""} · Correct: ${item.correct_option?.toUpperCase() || "—"}`}
                          </div>
                          {item.item_type === "video" && <VideoLink url={item.video_url} />}
                        </div>
                        <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                          <button className="btn btn-ghost btn-sm" title="Edit item" onClick={() => openEditItem(item)}><i className="ti ti-edit" /></button>
                          <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} title="Delete item" onClick={() => deleteItem(item.id)}><i className="ti ti-trash" /></button>
                        </div>
                      </div>
                    ))}

                    {/* Add item row */}
                    <div style={{ padding: "6px 14px 6px 44px" }}>
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--primary)", fontSize: ".8rem" }} onClick={() => openAddItem(section.id)}>
                        <i className="ti ti-plus mr-4" /> Add Item
                      </button>
                    </div>
                  </div>
                );
              })}

              {/* Unsectioned items */}
              {unsectioned.length > 0 && (
                <div className="settings-card" style={{ padding: 10 }}>
                  <div style={{ fontSize: ".78rem", color: sections.length === 0 ? "var(--on-variant)" : "var(--warning)", marginBottom: 8 }}>
                    <i className={`ti ${sections.length === 0 ? "ti-list" : "ti-alert-triangle"} mr-4`} />
                    {sections.length === 0 ? "Items" : "Items not assigned to any section"}
                  </div>
                  {unsectioned.map(item => (
                    <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", fontSize: ".84rem", borderBottom: "1px solid var(--outline-v)" }}>
                      <i className={`ti ${item.item_type === "video" ? "ti-player-play" : "ti-help-circle"}`} style={{ color: "var(--on-variant)", fontSize: 13, flexShrink: 0 }} />
                      <span style={{ flex: 1 }}>{item.title}</span>
                      <button className="btn btn-ghost btn-sm" title="Edit item" onClick={() => openEditItem(item)}><i className="ti ti-edit" /></button>
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} title="Delete item" onClick={() => deleteItem(item.id)}><i className="ti ti-trash" /></button>
                    </div>
                  ))}
                  <button className="btn btn-ghost btn-sm mt-8" style={{ color: "var(--primary)", fontSize: ".8rem" }} onClick={() => openAddItem(null)}>
                    <i className="ti ti-plus mr-4" /> Add Unsectioned Item
                  </button>
                </div>
              )}
            </div>
          )}

          {/* ── Section form ── */}
          {panelMode === "section" && (
            <div className="settings-card" style={{ padding: 16 }}>
              <div className="settings-card-title mb-12">{editSectionId ? "Edit Section" : "Add Section"}</div>
              {formErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{formErr}</div></div>}
              <div className="field-group mb-12">
                <label className="field-label">Title *</label>
                <input className="field-input" value={sectionForm.title} onChange={e => setSectionForm(p => ({ ...p, title: e.target.value }))} placeholder="e.g. Technical Knowledge" />
              </div>
              <div className="form-row cols-2 mb-12">
                <div className="field-group">
                  <label className="field-label">Order</label>
                  <input type="number" min={1} className="field-input" value={sectionForm.order} onChange={e => setSectionForm(p => ({ ...p, order: e.target.value }))} />
                </div>
                <div className="field-group">
                  <label className="field-label">Score (marks allocated)</label>
                  <input type="number" min={0} className="field-input" value={sectionForm.score} onChange={e => setSectionForm(p => ({ ...p, score: e.target.value }))} placeholder="e.g. 40" />
                </div>
              </div>
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="btn btn-ghost" onClick={closePanel} disabled={saving}>Cancel</button>
                <button className="btn btn-filled" onClick={saveSection} disabled={saving}>
                  {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : editSectionId ? "Update" : "Save"}
                </button>
              </div>
            </div>
          )}

          {/* ── Item form ── */}
          {panelMode === "item" && (
            <div className="settings-card" style={{ padding: 16 }}>
              <div className="settings-card-title mb-12">{editItemId ? "Edit Item" : "Add Item"}</div>
              {formErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{formErr}</div></div>}

              <div className="field-group mb-12">
                <label className="field-label">Item Type *</label>
                <select className="field-input field-select" value={itemForm.item_type}
                  onChange={e => { setItemForm(p => ({ ...p, item_type: e.target.value as "video" | "quiz" })); setQuestionType("mcq"); }}>
                  <option value="quiz">Quiz</option>
                  <option value="video">Video</option>
                </select>
              </div>

              <div className="field-group mb-12">
                <label className="field-label">Title *</label>
                <input className="field-input" value={itemForm.title} onChange={e => setItem("title", e.target.value)}
                  placeholder={itemForm.item_type === "video" ? "e.g. Company Introduction" : "e.g. HR Policy Question"} />
              </div>

              {itemForm.item_type === "video" && (
                <div className="form-row cols-2 mb-12">
                  <div className="field-group">
                    <label className="field-label">Video URL *</label>
                    <input className="field-input" value={itemForm.video_url} onChange={e => setItem("video_url", e.target.value)} placeholder="https://youtu.be/..." />
                    <VideoPreview url={itemForm.video_url} />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Duration (seconds)</label>
                    <input type="number" min={0} className="field-input" value={itemForm.duration_secs} onChange={e => setItem("duration_secs", e.target.value)} placeholder="180" />
                  </div>
                </div>
              )}

              {itemForm.item_type === "quiz" && (
                <>
                  <div className="field-group mb-12">
                    <label className="field-label">Question Type *</label>
                    <select className="field-input field-select" value={questionType} onChange={e => changeQuestionType(e.target.value as "mcq" | "truefalse")}>
                      <option value="mcq">Multiple Choice</option>
                      <option value="truefalse">True / False</option>
                    </select>
                  </div>
                  <div className="field-group mb-12">
                    <label className="field-label">Question *</label>
                    <input className="field-input" value={itemForm.question} onChange={e => setItem("question", e.target.value)} placeholder="e.g. What is the notice period?" />
                  </div>
                  <div className="form-row cols-2 mb-12">
                    {(questionType === "truefalse" ? ["a", "b"] as const : ["a", "b", "c", "d"] as const).map(opt => (
                      <div key={opt} className="field-group">
                        <label className="field-label">Option {opt.toUpperCase()} *</label>
                        <input className="field-input"
                          value={itemForm[`option_${opt}` as keyof ItemForm]}
                          onChange={e => setItem(`option_${opt}` as keyof ItemForm, e.target.value)}
                          placeholder={questionType === "truefalse" ? (opt === "a" ? "True" : "False") : `Option ${opt.toUpperCase()}`}
                          readOnly={questionType === "truefalse"} />
                      </div>
                    ))}
                  </div>
                  <div className="field-group mb-12">
                    <label className="field-label">Correct Option *</label>
                    <select className="field-input field-select" value={itemForm.correct_option} onChange={e => setItem("correct_option", e.target.value)}>
                      {(questionType === "truefalse" ? ["a", "b"] : ["a", "b", "c", "d"]).map(o => (
                        <option key={o} value={o}>{questionType === "truefalse" ? (o === "a" ? "True" : "False") : `Option ${o.toUpperCase()}`}</option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button className="btn btn-ghost" onClick={closePanel} disabled={saving}>Cancel</button>
                <button className="btn btn-filled" onClick={saveItem} disabled={saving}>
                  {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : editItemId ? "Update" : "Save"}
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="modal-footer">
          {!panelMode && (
            <button className="btn btn-ghost" onClick={openAddSection}>
              <i className="ti ti-plus" /> Add Section
            </button>
          )}
          <button className="btn btn-ghost" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>
  );
}
