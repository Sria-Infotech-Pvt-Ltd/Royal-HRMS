"use client";

import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import {
  validateTemplateForm, EMPTY_TEMPLATE_FORM, toSlug, catValue,
  ATTACHMENT_ACCEPT_ATTR, fileKind, FILE_KIND_META, formatBytes,
  EMAIL_TEMPLATE_CATEGORIES, emailTemplateDetail, emailTemplateAttachmentDetail, parseAvailableVars,
  type ApiAttachment, type ApiEmailTemplate, type ApiTemplateCategory, type TemplateForm, type TemplateFormErrors,
} from "../_data";

interface Props {
  template: ApiEmailTemplate | null;   // null = add mode
  saving:   boolean;
  onClose:  () => void;
  onSave:   (form: TemplateForm) => Promise<void>;
}

const TOOLBAR = [
  { cmd: "bold",                icon: "ti-bold",             tip: "Bold"          },
  { cmd: "italic",              icon: "ti-italic",           tip: "Italic"        },
  { cmd: "underline",           icon: "ti-underline",        tip: "Underline"     },
  { cmd: "strikeThrough",       icon: "ti-strikethrough",    tip: "Strikethrough" },
  { cmd: "|" },
  { cmd: "insertUnorderedList", icon: "ti-list",             tip: "Bullet list"   },
  { cmd: "insertOrderedList",   icon: "ti-list-numbers",     tip: "Numbered list" },
  { cmd: "|" },
  { cmd: "justifyLeft",         icon: "ti-align-left",       tip: "Align left"    },
  { cmd: "justifyCenter",       icon: "ti-align-center",     tip: "Align center"  },
  { cmd: "justifyRight",        icon: "ti-align-right",      tip: "Align right"   },
  { cmd: "|" },
  { cmd: "createLink",          icon: "ti-link",             tip: "Insert link"   },
  { cmd: "unlink",              icon: "ti-unlink",           tip: "Remove link"   },
  { cmd: "|" },
  { cmd: "insertImage",         icon: "ti-photo",            tip: "Insert image"  },
  { cmd: "|" },
  { cmd: "removeFormat",        icon: "ti-clear-formatting", tip: "Clear format"  },
];

export default function EditTemplateModal({ template, saving, onClose, onSave }: Props) {
  const isAddMode = template === null;

  const [form,       setForm]       = useState<TemplateForm>(
    isAddMode
      ? { ...EMPTY_TEMPLATE_FORM }
      : { name: template.name, display_name: template.display_name, template_type: template.template_type, subject: template.subject, body: template.body, attachments: [], available_variables: parseAvailableVars(template.available_variables) }
  );
  const [slugEdited,         setSlugEdited]         = useState(false);
  const [categories,         setCategories]         = useState<ApiTemplateCategory[]>([]);
  const [catLoading,         setCatLoading]         = useState(true);
  const [catSearch,          setCatSearch]          = useState("");
  const [catOpen,            setCatOpen]            = useState(false);
  const [catCreating,        setCatCreating]        = useState(false);
  const [existingAttachments, setExistingAttachments] = useState<ApiAttachment[]>(
    !isAddMode ? (template.attachments ?? []) : []
  );
  const [removedAttachmentIds, setRemovedAttachmentIds] = useState<number[]>([]);
  const [dragOver,   setDragOver]   = useState(false);
  const fileInputRef  = useRef<HTMLInputElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const [errors,     setErrors]     = useState<TemplateFormErrors>({});
  const [viewSource, setViewSource] = useState(false);
  const [mobileTab,  setMobileTab]  = useState<"editor" | "preview" | "sidebar">("editor");

  // ── Image editing state ────────────────────────────────────────────────────
  const [selImg,    setSelImg]    = useState<HTMLImageElement | null>(null);
  const [imgWidth,  setImgWidth]  = useState(0);
  type CropState = {
    src: string; natW: number; natH: number; dispW: number; dispH: number;
    sel: { x: number; y: number; w: number; h: number };
    drag: boolean; start: { x: number; y: number };
  };
  const [cropState, setCropState] = useState<CropState | null>(null);

  const editorRef = useRef<HTMLDivElement>(null);

  // Seed the editor when switching back from source view. Deliberately keyed
  // only on viewSource, not form.body — the contentEditable div owns the body
  // text while editing; re-seeding on every form.body change would overwrite
  // the caret position and undo history mid-edit.
  useEffect(() => {
    if (!viewSource && editorRef.current) {
      editorRef.current.innerHTML = form.body;
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewSource]);

  // Seed on first mount only — same reasoning as above, form.body is
  // intentionally excluded so this doesn't re-run as the user types.
  useEffect(() => {
    if (editorRef.current) editorRef.current.innerHTML = form.body;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch categories
  useEffect(() => {
    setCatLoading(true);
    clientApi.get(EMAIL_TEMPLATE_CATEGORIES)
      .then(res => {
        const data = res.data.data ?? res.data;
        setCategories(Array.isArray(data) ? data : []);
      })
      .catch(() => {})
      .finally(() => setCatLoading(false));
  }, []);

  // Fetch full template detail to get existing attachments (list API omits
  // them). Deliberately runs once on mount — template.id is fixed for the
  // lifetime of this modal instance (a different template reopens it fresh).
  useEffect(() => {
    if (isAddMode) return;
    clientApi.get(emailTemplateDetail(template.id))
      .then(res => {
        const detail: ApiEmailTemplate = res.data.data ?? res.data;
        if (Array.isArray(detail.attachments) && detail.attachments.length > 0) {
          setExistingAttachments(detail.attachments as ApiAttachment[]);
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function syncBody() {
    if (editorRef.current) setForm(p => ({ ...p, body: editorRef.current!.innerHTML }));
  }

  function execCmd(cmd: string) {
    if (cmd === "insertImage") {
      imageInputRef.current?.click();
      return;
    }
    if (cmd === "createLink") {
      const url = window.prompt("Enter URL:");
      if (url) document.execCommand("createLink", false, url);
    } else {
      document.execCommand(cmd, false);
    }
    syncBody();
    editorRef.current?.focus();
  }

  function handleImageInsert(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = ev => {
      const src = ev.target?.result as string;
      editorRef.current?.focus();
      document.execCommand(
        "insertHTML", false,
        `<img src="${src}" style="max-width:100%;height:auto;display:inline-block;vertical-align:middle;margin:4px 2px;border-radius:4px;cursor:pointer" />`
      );
      syncBody();
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  // ── Image editing helpers ──────────────────────────────────────────────────

  function handleEditorClick(e: React.MouseEvent<HTMLDivElement>) {
    const t = e.target as HTMLElement;
    if (t.tagName === "IMG") {
      const img = t as HTMLImageElement;
      setSelImg(img);
      setImgWidth(img.offsetWidth || img.naturalWidth);
    } else if (!(t as HTMLElement).closest("[data-img-toolbar]")) {
      setSelImg(null);
    }
  }

  function resizeImg(w: number) {
    if (!selImg || w < 10) return;
    const ratio = selImg.naturalHeight / selImg.naturalWidth;
    selImg.style.width  = `${w}px`;
    selImg.style.height = `${Math.round(w * ratio)}px`;
    syncBody();
  }

  function alignImg(align: "left" | "center" | "right") {
    if (!selImg) return;
    if (align === "left") {
      selImg.style.float = "left"; selImg.style.display = "inline-block";
      selImg.style.marginLeft = "0"; selImg.style.marginRight = "10px";
    } else if (align === "right") {
      selImg.style.float = "right"; selImg.style.display = "inline-block";
      selImg.style.marginLeft = "10px"; selImg.style.marginRight = "0";
    } else {
      selImg.style.float = "none"; selImg.style.display = "block";
      selImg.style.marginLeft = "auto"; selImg.style.marginRight = "auto";
    }
    syncBody();
  }

  function deleteImg() {
    if (!selImg) return;
    selImg.remove();
    setSelImg(null);
    syncBody();
  }

  function openCrop() {
    if (!selImg) return;
    const src  = selImg.src;
    const natW = selImg.naturalWidth;
    const natH = selImg.naturalHeight;
    const maxW = 680, maxH = 480;
    const scale = Math.min(1, maxW / natW, maxH / natH);
    const dispW = Math.round(natW * scale);
    const dispH = Math.round(natH * scale);
    setCropState({ src, natW, natH, dispW, dispH, sel: { x: 0, y: 0, w: dispW, h: dispH }, drag: false, start: { x: 0, y: 0 } });
  }

  function cropDown(e: React.MouseEvent<HTMLDivElement>) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, e.clientX - r.left);
    const y = Math.max(0, e.clientY - r.top);
    setCropState(p => p ? { ...p, drag: true, start: { x, y }, sel: { x, y, w: 0, h: 0 } } : p);
  }

  function cropMove(e: React.MouseEvent<HTMLDivElement>) {
    if (!cropState?.drag) return;
    const r  = e.currentTarget.getBoundingClientRect();
    const cx = Math.max(0, Math.min(e.clientX - r.left, cropState.dispW));
    const cy = Math.max(0, Math.min(e.clientY - r.top,  cropState.dispH));
    const nx = Math.min(cropState.start.x, cx);
    const ny = Math.min(cropState.start.y, cy);
    const nw = Math.abs(cx - cropState.start.x);
    const nh = Math.abs(cy - cropState.start.y);
    setCropState(p => p ? { ...p, sel: { x: nx, y: ny, w: nw, h: nh } } : p);
  }

  function cropUp() {
    setCropState(p => p ? { ...p, drag: false } : p);
  }

  function applyCrop() {
    if (!cropState || !selImg || cropState.sel.w < 4 || cropState.sel.h < 4) return;
    const { src, natW, natH, dispW, dispH, sel } = cropState;
    const scaleX = natW / dispW;
    const scaleY = natH / dispH;
    const cw = Math.round(sel.w * scaleX);
    const ch = Math.round(sel.h * scaleY);
    const canvas = document.createElement("canvas");
    canvas.width  = cw;
    canvas.height = ch;
    const ctx = canvas.getContext("2d")!;
    const img = new window.Image();
    img.onload = () => {
      ctx.drawImage(img, Math.round(sel.x * scaleX), Math.round(sel.y * scaleY), cw, ch, 0, 0, cw, ch);
      const newSrc = canvas.toDataURL("image/png");
      selImg.src = newSrc;
      selImg.style.width  = `${Math.min(cw, 600)}px`;
      selImg.style.height = "auto";
      setImgWidth(Math.min(cw, 600));
      setCropState(null);
      syncBody();
    };
    img.src = src;
  }

  function insertTag(tag: string) {
    if (viewSource) {
      setForm(p => ({ ...p, body: p.body + tag }));
      return;
    }
    editorRef.current?.focus();
    document.execCommand("insertText", false, tag);
    syncBody();
  }

  function addFiles(files: FileList | null) {
    if (!files) return;
    const incoming = Array.from(files);
    setForm(p => ({
      ...p,
      attachments: [
        ...p.attachments,
        ...incoming.filter(f => !p.attachments.some(a => a.name === f.name && a.size === f.size)),
      ],
    }));
  }

  function removeFile(index: number) {
    setForm(p => ({ ...p, attachments: p.attachments.filter((_, i) => i !== index) }));
  }

  function removeExistingAttachment(id: number) {
    setExistingAttachments(prev => prev.filter(a => a.id !== id));
    setRemovedAttachmentIds(prev => [...prev, id]);
  }

  async function handleCreateCategory() {
    const displayName = catSearch.trim();
    if (!displayName || catCreating) return;
    setCatCreating(true);
    try {
      const res = await clientApi.post(EMAIL_TEMPLATE_CATEGORIES, {
        name:         toSlug(displayName),
        display_name: displayName,
      });
      const newCat: ApiTemplateCategory = res.data.data ?? res.data;
      const value = catValue(newCat);
      setCategories(prev => [...prev, newCat]);
      setForm(p => ({ ...p, template_type: value }));
      setCatSearch(newCat.name);
      setCatOpen(false);
      setErrors(p => ({ ...p, template_type: undefined }));
    } catch {
      // leave dropdown open so user can retry
    } finally {
      setCatCreating(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    addFiles(e.dataTransfer.files);
  }

  async function handleSave() {
    syncBody();
    const latestBody = editorRef.current?.innerHTML ?? form.body;
    const latest: TemplateForm = {
      ...form,
      body:                latestBody,
      available_variables: [...new Set([...predefined, ...detectedTags])],
    };
    const errs = validateTemplateForm(latest, isAddMode);
    if (Object.keys(errs).length) { setErrors(errs); return; }

    // Delete any existing attachments the user removed (fire-and-forget, don't block save)
    if (!isAddMode && removedAttachmentIds.length > 0) {
      await Promise.allSettled(
        removedAttachmentIds.map(aid =>
          clientApi.delete(emailTemplateAttachmentDetail(template!.id, aid))
        )
      );
    }

    await onSave(latest);
  }

  // Highlight {VARIABLE} tokens with a coloured span (safe for raw text and HTML bodies)
  function highlightVars(html: string): string {
    return html.replace(
      /\{([A-Za-z][A-Za-z0-9_]*)\}/g,
      '<span style="background:rgba(234,167,0,0.18);color:#a06800;padding:1px 5px;border-radius:3px;font-family:ui-monospace,monospace;font-size:0.88em;font-weight:600">{$1}</span>'
    );
  }

  // Extract {VARIABLE} tokens from subject + body (strips HTML tags before scanning body)
  const detectedTags = (() => {
    const plainBody = form.body.replace(/<[^>]*>/g, " ");
    const matches   = [...`${form.subject} ${plainBody}`.matchAll(/\{([A-Za-z][A-Za-z0-9_]*)\}/g)];
    return [...new Set(matches.map(m => m[1]))];
  })();

  // Predefined variables from the saved template (edit mode only)
  // parseAvailableVars handles the backend returning a JSON-stringified string
  const predefined: string[] = !isAddMode
    ? parseAvailableVars(template.available_variables)
    : [];

  // Sidebar shows predefined first, then any newly typed ones not already in predefined
  const newTags  = detectedTags.filter(v => !predefined.includes(v));
  const variables = predefined;

  return (
    <>
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal et-modal-wrap" style={{ width: "min(1280px, 96vw)", maxHeight: "92vh", overflow: "hidden", display: "flex", flexDirection: "column" }}>

        {/* ── Header ── */}
        <div className="modal-header" style={{ flexShrink: 0 }}>
          <div style={{ minWidth: 0 }}>
            <div className="modal-title">
              {isAddMode
                ? "Add Email Template"
                : <>Edit — <span style={{ color: "var(--primary)" }}>{template.display_name}</span></>
              }
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
              {isAddMode
                ? "Fill in the subject and body for the new template"
                : template.description
              }
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close" suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>

        {/* ── Mobile tab bar (hidden on desktop via CSS) ── */}
        <div className="et-tab-bar" style={{ display: "none", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)", flexShrink: 0 }}>
          {(["editor", "preview", "sidebar"] as const).map(tab => (
            <button key={tab} type="button" suppressHydrationWarning
              className={`et-tab-btn${mobileTab === tab ? " et-tab-btn-active" : ""}`}
              onClick={() => setMobileTab(tab)}
              style={{ flex: 1, padding: "10px 4px", background: "none", border: "none", borderBottom: `2px solid ${mobileTab === tab ? "var(--primary)" : "transparent"}`, cursor: "pointer", fontSize: 12, fontWeight: mobileTab === tab ? 600 : 400, color: mobileTab === tab ? "var(--primary)" : "var(--on-variant)", fontFamily: "inherit", transition: "color 0.15s" }}>
              {tab === "editor" ? "Editor" : tab === "preview" ? "Preview" : "Variables"}
            </button>
          ))}
        </div>

        {/* ── Editor + preview + sidebar ── */}
        <div className="et-modal-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 180px", flex: 1, minHeight: 0, overflow: "hidden" }}>

          {/* Left: fields + editor */}
          <div className={`et-col-editor${mobileTab === "editor" ? " et-tab-active" : ""}`} style={{ display: "flex", flexDirection: "column", overflow: "hidden", borderRight: "1px solid var(--outline-v)" }}>
            <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px", display: "flex", flexDirection: "column", gap: 14 }}>

              {/* Display Name + slug — add mode only */}
              {isAddMode && (
                <>
                  <div className="field-group">
                    <label className="field-label">Display Name <span style={{ color: "var(--error)" }}>*</span></label>
                    <input className="field-input" placeholder="e.g. Pay Slip, Birthday Wish"
                      value={form.display_name}
                      onChange={e => {
                        const val = e.target.value;
                        setForm(p => ({
                          ...p,
                          display_name: val,
                          name: slugEdited ? p.name : toSlug(val),
                        }));
                        setErrors(p => ({ ...p, display_name: undefined }));
                      }}
                      suppressHydrationWarning />
                    {errors.display_name && <span className="field-error">{errors.display_name}</span>}
                  </div>

                  <div className="field-group">
                    <label className="field-label" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      Slug (name) <span style={{ color: "var(--error)" }}>*</span>
                      <span style={{ fontSize: 10, color: "var(--outline)", fontWeight: 400 }}>auto-generated · lowercase_with_underscores</span>
                    </label>
                    <input className="field-input" placeholder="e.g. pay_slip"
                      value={form.name}
                      onChange={e => {
                        setSlugEdited(true);
                        setForm(p => ({ ...p, name: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, "") }));
                        setErrors(p => ({ ...p, name: undefined }));
                      }}
                      style={{ fontFamily: "ui-monospace, monospace", fontSize: 12 }}
                      suppressHydrationWarning />
                    {errors.name && <span className="field-error">{errors.name}</span>}
                  </div>
                </>
              )}

              {/* Category combobox — searchable + inline create */}
              <div className="field-group">
                <label className="field-label">
                  Category <span style={{ color: "var(--error)" }}>*</span>
                </label>

                {catLoading ? (
                  <div style={{ fontSize: 12, color: "var(--on-variant)", padding: "8px 0", display: "flex", alignItems: "center", gap: 6 }}>
                    <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Loading categories…
                  </div>

                ) : isAddMode ? (() => {
                  const filtered   = catSearch.trim()
                    ? categories.filter(c => c.name.toLowerCase().includes(catSearch.toLowerCase()))
                    : categories;
                  const exactMatch = categories.some(c => c.name.toLowerCase() === catSearch.trim().toLowerCase());
                  return (
                    <div style={{ position: "relative" }}>
                      {/* Input */}
                      <div style={{ position: "relative", width: "100%" }}>
                        <input
                          className="field-input"
                          placeholder="Search or create category…"
                          value={catSearch}
                          autoComplete="off"
                          suppressHydrationWarning
                          style={{ width: "100%", paddingRight: 30, borderColor: (errors as Record<string,string|undefined>).template_type ? "var(--error)" : undefined }}
                          onFocus={() => setCatOpen(true)}
                          onBlur={() => setTimeout(() => setCatOpen(false), 160)}
                          onChange={e => {
                            setCatSearch(e.target.value);
                            setCatOpen(true);
                            setForm(p => ({ ...p, template_type: "" }));
                            setErrors(p => ({ ...p, template_type: undefined }));
                          }}
                        />
                        {catSearch ? (
                          <button type="button" suppressHydrationWarning
                            onMouseDown={e => e.preventDefault()}
                            onClick={() => { setCatSearch(""); setForm(p => ({ ...p, template_type: "" })); setCatOpen(false); }}
                            style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", cursor: "pointer", color: "var(--outline)", padding: 2, lineHeight: 1 }}>
                            <i className="ti ti-x" style={{ fontSize: 13 }} />
                          </button>
                        ) : (
                          <i className="ti ti-chevron-down" style={{ position: "absolute", right: 9, top: "50%", transform: "translateY(-50%)", fontSize: 13, color: "var(--outline)", pointerEvents: "none" }} />
                        )}
                      </div>

                      {/* Dropdown */}
                      {catOpen && (
                        <div style={{ position: "absolute", top: "calc(100% + 3px)", left: 0, right: 0, background: "#fff", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", boxShadow: "0 4px 18px rgba(0,0,0,0.1)", zIndex: 300, overflow: "hidden" }}>
                          <div style={{ maxHeight: 186, overflowY: "auto" }}>
                            {filtered.length === 0 && !catSearch.trim() && (
                              <div style={{ padding: "10px 14px", fontSize: 12, color: "var(--on-variant)" }}>No categories yet</div>
                            )}
                            {filtered.map(cat => {
                              const val       = catValue(cat);
                              const isSelected = form.template_type === val;
                              return (
                                <button key={cat.id} type="button"
                                  onMouseDown={e => e.preventDefault()}
                                  onClick={() => {
                                    setForm(p => ({ ...p, template_type: val }));
                                    setCatSearch(cat.name);
                                    setCatOpen(false);
                                    setErrors(p => ({ ...p, template_type: undefined }));
                                  }}
                                  style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", padding: "8px 12px", background: isSelected ? "rgba(30,78,140,0.07)" : "none", border: "none", cursor: "pointer", fontSize: 13, color: "var(--on-bg)", textAlign: "left" }}
                                  onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = "var(--bg-low)"; }}
                                  onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = isSelected ? "rgba(30,78,140,0.07)" : "none"; }}>
                                  <i className="ti ti-check" style={{ fontSize: 12, color: "var(--primary)", visibility: isSelected ? "visible" : "hidden", flexShrink: 0 }} />
                                  {cat.name}
                                </button>
                              );
                            })}
                          </div>

                          {/* Create new */}
                          {catSearch.trim() && !exactMatch && (
                            <div style={{ borderTop: filtered.length ? "1px solid var(--outline-v)" : "none" }}>
                              <button type="button"
                                onMouseDown={e => e.preventDefault()}
                                onClick={handleCreateCategory}
                                disabled={catCreating}
                                style={{ display: "flex", alignItems: "center", gap: 7, width: "100%", padding: "8px 12px", background: "none", border: "none", cursor: catCreating ? "default" : "pointer", fontSize: 13, color: "var(--primary)", textAlign: "left", opacity: catCreating ? 0.65 : 1 }}
                                onMouseEnter={e => { if (!catCreating) e.currentTarget.style.background = "rgba(30,78,140,0.06)"; }}
                                onMouseLeave={e => { e.currentTarget.style.background = "none"; }}>
                                {catCreating
                                  ? <><i className="ti ti-loader-2" style={{ fontSize: 13, animation: "spin 1s linear infinite" }} /> Creating…</>
                                  : <><i className="ti ti-plus" style={{ fontSize: 13 }} /> Create &ldquo;{catSearch.trim()}&rdquo;</>
                                }
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })() : (
                  /* Edit mode — category locked, show read-only */
                  <select className="field-input" value={form.template_type} disabled suppressHydrationWarning
                    style={{ cursor: "default", color: form.template_type ? "var(--on-bg)" : "var(--outline)" }}>
                    {categories.map(cat => <option key={cat.id} value={catValue(cat)}>{cat.name}</option>)}
                    {!categories.some(c => catValue(c) === form.template_type) && (
                      <option value={form.template_type}>{template?.template_type_display ?? form.template_type}</option>
                    )}
                  </select>
                )}

                {(errors as Record<string, string | undefined>).template_type && (
                  <span className="field-error">{(errors as Record<string, string | undefined>).template_type}</span>
                )}
                {!isAddMode && (
                  <span style={{ fontSize: 11, color: "var(--outline)", marginTop: 2 }}>Category cannot be changed after creation.</span>
                )}
              </div>

              {/* Subject */}
              <div className="field-group">
                <label className="field-label">Subject <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder="Email subject line…"
                  value={form.subject}
                  onChange={e => { setForm(p => ({ ...p, subject: e.target.value })); setErrors(p => ({ ...p, subject: undefined })); }}
                  suppressHydrationWarning />
                {errors.subject && <span className="field-error">{errors.subject}</span>}
              </div>

              {/* Body */}
              <div className="field-group" style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <label className="field-label" style={{ marginBottom: 0 }}>
                    Body <span style={{ color: "var(--error)" }}>*</span>
                  </label>
                  <button type="button" suppressHydrationWarning
                    onClick={() => { syncBody(); setSelImg(null); setViewSource(v => !v); }}
                    style={{ fontSize: 11, color: "var(--primary)", background: "none", border: "none", cursor: "pointer", fontFamily: "inherit", display: "flex", alignItems: "center", gap: 4 }}>
                    <i className={`ti ${viewSource ? "ti-eye" : "ti-code"}`} style={{ fontSize: 13 }} />
                    {viewSource ? "Visual" : "HTML source"}
                  </button>
                </div>

                {/* Toolbar */}
                {!viewSource && (
                  <div style={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap", padding: "5px 8px", border: "1.5px solid var(--outline-v)", borderBottom: "none", borderRadius: "var(--radius) var(--radius) 0 0", background: "var(--bg-low)" }}>
                    {TOOLBAR.map((btn, i) =>
                      btn.cmd === "|" ? (
                        <div key={i} style={{ width: 1, height: 16, background: "var(--outline-v)", margin: "0 3px" }} />
                      ) : (
                        <button key={btn.cmd} type="button" title={btn.tip} suppressHydrationWarning
                          onMouseDown={e => { e.preventDefault(); execCmd(btn.cmd!); }}
                          style={{ width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center", background: "none", border: "none", borderRadius: 4, cursor: "pointer", color: "var(--on-variant)", fontSize: 14 }}
                          onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-mid)")}
                          onMouseLeave={e => (e.currentTarget.style.background = "none")}>
                          <i className={`ti ${btn.icon}`} />
                        </button>
                      )
                    )}
                  </div>
                )}

                {/* Image controls bar — shown when an image is selected */}
                {selImg && !viewSource && (
                  <div data-img-toolbar="true" style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", padding: "5px 10px", background: "var(--primary)", borderLeft: "1.5px solid var(--primary)", borderRight: "1.5px solid var(--primary)" }}>
                    <span style={{ fontSize: 11, color: "#fff", fontWeight: 600, marginRight: 2 }}>Image</span>
                    <div style={{ width: 1, height: 14, background: "rgba(255,255,255,0.3)" }} />

                    {/* Width */}
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span style={{ fontSize: 11, color: "rgba(255,255,255,0.8)" }}>W:</span>
                      <input type="number" min={10} max={1200} value={imgWidth}
                        onChange={e => { const w = +e.target.value; setImgWidth(w); resizeImg(w); }}
                        style={{ width: 58, height: 22, fontSize: 11, padding: "0 6px", borderRadius: 4, border: "none", background: "rgba(255,255,255,0.9)", outline: "none" }}
                        suppressHydrationWarning />
                      <span style={{ fontSize: 11, color: "rgba(255,255,255,0.8)" }}>px</span>
                    </div>
                    <div style={{ width: 1, height: 14, background: "rgba(255,255,255,0.3)" }} />

                    {/* Align */}
                    {(["left","center","right"] as const).map(a => (
                      <button key={a} type="button" title={`Align ${a}`} suppressHydrationWarning
                        onMouseDown={e => { e.preventDefault(); alignImg(a); }}
                        style={{ width: 26, height: 26, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 4, color: "#fff", cursor: "pointer", fontSize: 13 }}>
                        <i className={`ti ti-align-${a}`} />
                      </button>
                    ))}
                    <div style={{ width: 1, height: 14, background: "rgba(255,255,255,0.3)" }} />

                    {/* Crop */}
                    <button type="button" title="Crop image" suppressHydrationWarning
                      onMouseDown={e => { e.preventDefault(); openCrop(); }}
                      style={{ display: "flex", alignItems: "center", gap: 5, height: 26, padding: "0 9px", background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 4, color: "#fff", cursor: "pointer", fontSize: 11 }}>
                      <i className="ti ti-crop" style={{ fontSize: 13 }} /> Crop
                    </button>

                    {/* Delete */}
                    <button type="button" title="Remove image" suppressHydrationWarning
                      onMouseDown={e => { e.preventDefault(); deleteImg(); }}
                      style={{ display: "flex", alignItems: "center", gap: 5, height: 26, padding: "0 9px", background: "rgba(239,68,68,0.35)", border: "none", borderRadius: 4, color: "#fff", cursor: "pointer", fontSize: 11, marginLeft: "auto" }}>
                      <i className="ti ti-trash" style={{ fontSize: 13 }} /> Remove
                    </button>
                  </div>
                )}

                {/* Visual editor */}
                {!viewSource && (
                  <div ref={editorRef} contentEditable suppressContentEditableWarning
                    onInput={syncBody} onBlur={syncBody} onClick={handleEditorClick}
                    style={{ flex: 1, minHeight: 200, padding: "12px 14px", border: "1.5px solid var(--outline-v)", borderRadius: selImg ? "0 0 var(--radius) var(--radius)" : "0 0 var(--radius) var(--radius)", outline: "none", overflowY: "auto", fontSize: 13, lineHeight: 1.7, color: "var(--on-bg)", background: "#fff", fontFamily: "inherit" }}
                  />
                )}

                {/* HTML source */}
                {viewSource && (
                  <textarea value={form.body} suppressHydrationWarning
                    onChange={e => setForm(p => ({ ...p, body: e.target.value }))}
                    style={{ flex: 1, minHeight: 200, resize: "vertical", padding: "12px 14px", border: "1.5px solid var(--outline-v)", borderRadius: "var(--radius)", fontFamily: "ui-monospace, monospace", fontSize: 12, lineHeight: 1.7, outline: "none", color: "var(--on-bg)" }}
                    onFocus={e => (e.currentTarget.style.borderColor = "var(--primary)")}
                    onBlur={e => (e.currentTarget.style.borderColor = "var(--outline-v)")}
                  />
                )}

                {errors.body && <span className="field-error">{errors.body}</span>}
              </div>

              <div style={{ height: 4, flexShrink: 0 }} />
            </div>
          </div>

          {/* Middle: live preview */}
          <div className={`et-col-preview${mobileTab === "preview" ? " et-tab-active" : ""}`} style={{ overflowY: "auto", borderRight: "1px solid var(--outline-v)", background: "#fafbfc", display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "14px 14px 10px", flexShrink: 0 }}>
              Live Preview
            </div>
            <div style={{ padding: "0 14px 16px", flex: 1, overflowY: "auto" }}>
              {/* Subject preview */}
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Subject</div>
              <div style={{ fontSize: 12, color: "var(--on-bg)", marginBottom: 14, padding: "8px 10px", background: "#fff", borderRadius: 6, border: "1px solid var(--outline-v)", lineHeight: 1.5, wordBreak: "break-word" }}
                dangerouslySetInnerHTML={{ __html: highlightVars(form.subject) || '<span style="color:var(--outline);font-style:italic">No subject yet…</span>' }} />

              {/* Body preview */}
              <div style={{ fontSize: 10, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 4 }}>Body</div>
              {form.body ? (
                <div style={{ fontSize: 12, lineHeight: 1.75, padding: "12px 12px", background: "#fff", borderRadius: 6, border: "1px solid var(--outline-v)", wordBreak: "break-word", overflowX: "auto" }}
                  dangerouslySetInnerHTML={{ __html: highlightVars(form.body) }} />
              ) : (
                <div style={{ fontSize: 12, color: "var(--outline)", fontStyle: "italic", padding: "12px 12px", background: "#fff", borderRadius: 6, border: "1px solid var(--outline-v)" }}>
                  Body will appear here…
                </div>
              )}
            </div>
          </div>

          {/* Right: variable tags sidebar */}
          <div className={`et-col-sidebar${mobileTab === "sidebar" ? " et-tab-active" : ""}`} style={{ overflowY: "auto", background: "var(--bg-low)" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "14px 14px 10px" }}>
              Available Tags
            </div>

            {/* Predefined variables */}
            {variables.length > 0 && (
              <div style={{ padding: "0 10px 10px", display: "flex", flexDirection: "column", gap: 4 }}>
                {variables.map(v => {
                  const tag = `{${v}}`;
                  return (
                    <button key={v} type="button" suppressHydrationWarning
                      onClick={() => insertTag(tag)}
                      title={`Insert ${tag}`}
                      style={{ textAlign: "left", padding: "5px 9px", background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.12)", borderRadius: 4, fontSize: 11, fontFamily: "ui-monospace, monospace", color: "var(--primary)", cursor: "pointer" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "rgba(30,78,140,0.14)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "rgba(30,78,140,0.06)")}>
                      {tag}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Newly typed tags detected in subject/body */}
            {newTags.length > 0 && (
              <>
                <div style={{ fontSize: 10, fontWeight: 700, color: "var(--outline)", letterSpacing: "0.08em", textTransform: "uppercase", padding: "8px 14px 6px", borderTop: variables.length ? "1px solid var(--outline-v)" : "none" }}>
                  Detected Tags
                </div>
                <div style={{ padding: "0 10px 14px", display: "flex", flexDirection: "column", gap: 4 }}>
                  {newTags.map(v => {
                    const tag = `{${v}}`;
                    return (
                      <button key={v} type="button" suppressHydrationWarning
                        onClick={() => insertTag(tag)}
                        title={`Insert ${tag}`}
                        style={{ textAlign: "left", padding: "5px 9px", background: "rgba(234,167,0,0.08)", border: "1px solid rgba(234,167,0,0.3)", borderRadius: 4, fontSize: 11, fontFamily: "ui-monospace, monospace", color: "#a06800", cursor: "pointer" }}
                        onMouseEnter={e => (e.currentTarget.style.background = "rgba(234,167,0,0.16)")}
                        onMouseLeave={e => (e.currentTarget.style.background = "rgba(234,167,0,0.08)")}>
                        {tag}
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            {variables.length === 0 && newTags.length === 0 && (
              <div style={{ padding: "8px 14px 14px", fontSize: 12, color: "var(--on-variant)", lineHeight: 1.5 }}>
                Type <code style={{ fontSize: 11 }}>{"{VARIABLE}"}</code> in the subject or body to see tags here.
              </div>
            )}

            {/* Last updated */}
            {!isAddMode && (
              <div style={{ borderTop: "1px solid var(--outline-v)", padding: "12px 14px", fontSize: 11, color: "var(--outline)" }}>
                <div style={{ marginBottom: 2 }}>Last updated</div>
                <div style={{ color: "var(--on-variant)", fontWeight: 500 }}>
                  {new Date(template.updated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </div>
                {template.is_builtin && (
                  <div style={{ marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
                    <i className="ti ti-shield-check" style={{ fontSize: 12, color: "var(--success)" }} />
                    <span style={{ color: "var(--success)", fontWeight: 600, fontSize: 11 }}>Built-in template</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Attachment bar ── */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          style={{
            flexShrink: 0,
            borderTop: `1.5px ${dragOver ? "dashed" : "solid"} ${dragOver ? "var(--primary)" : "var(--outline-v)"}`,
            background: dragOver ? "rgba(30,78,140,0.03)" : "var(--bg-low)",
            padding: "10px 20px",
            display: "flex",
            alignItems: "center",
            gap: 10,
            minHeight: 52,
            transition: "background 0.12s, border-color 0.12s",
          }}>

          {/* Hidden image input for inline insertion */}
          <input ref={imageInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleImageInsert} suppressHydrationWarning />

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ATTACHMENT_ACCEPT_ATTR}
            style={{ display: "none" }}
            onChange={e => { addFiles(e.target.files); e.target.value = ""; }}
            suppressHydrationWarning
          />

          {/* Attach button */}
          <button type="button" suppressHydrationWarning
            onClick={() => fileInputRef.current?.click()}
            style={{ display: "flex", alignItems: "center", gap: 5, padding: "5px 12px", background: "none", border: "1.5px solid var(--outline-v)", borderRadius: "var(--radius)", cursor: "pointer", fontSize: 12, color: "var(--on-variant)", fontFamily: "inherit", flexShrink: 0, whiteSpace: "nowrap" }}
            onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--primary)"; e.currentTarget.style.color = "var(--primary)"; }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--outline-v)"; e.currentTarget.style.color = "var(--on-variant)"; }}>
            <i className="ti ti-paperclip" style={{ fontSize: 14 }} />
            Attach files
          </button>

          {/* Attachment chips — existing (saved) + new (pending upload) */}
          {existingAttachments.length === 0 && form.attachments.length === 0 ? (
            <span style={{ fontSize: 12, color: "var(--outline)", fontStyle: "italic" }}>
              {dragOver ? "Drop to attach…" : "PDF, Word, Excel, images"}
            </span>
          ) : (
            <div style={{ display: "flex", gap: 6, overflowX: "auto", flex: 1, alignItems: "center", paddingBottom: 2 }}>

              {/* ── Saved attachments from server ── */}
              {existingAttachments.map(att => {
                const isImg = att.mime_type.startsWith("image/");
                return (
                  <div key={`saved-${att.id}`} title={`${att.filename} · ${formatBytes(att.size)}`} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "4px 8px 4px 7px",
                    background: "rgba(30,78,140,0.05)", border: "1px solid rgba(30,78,140,0.18)",
                    borderRadius: 20, flexShrink: 0, maxWidth: 200,
                  }}>
                    {isImg ? (
                      <i className="ti ti-photo" style={{ fontSize: 11, color: "var(--primary)", flexShrink: 0 }} />
                    ) : (
                      <i className="ti ti-paperclip" style={{ fontSize: 11, color: "var(--primary)", flexShrink: 0 }} />
                    )}
                    <span style={{ fontSize: 11, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 120 }}>
                      {att.filename}
                    </span>
                    <span style={{ fontSize: 10, color: "var(--outline)", flexShrink: 0 }}>
                      {formatBytes(att.size)}
                    </span>
                    <button type="button" suppressHydrationWarning
                      onClick={() => removeExistingAttachment(att.id)}
                      title="Remove attachment"
                      style={{ background: "none", border: "none", cursor: "pointer", padding: 0, lineHeight: 1, color: "var(--outline)", flexShrink: 0 }}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--outline)")}>
                      <i className="ti ti-x" style={{ fontSize: 11 }} />
                    </button>
                  </div>
                );
              })}

              {/* ── New files (pending upload) ── */}
              {form.attachments.map((file, i) => {
                const kind = fileKind(file);
                const meta = FILE_KIND_META[kind];
                const isImg = kind === "image";
                return (
                  <div key={`new-${file.name}-${i}`} title={`${file.name} · ${formatBytes(file.size)} — will be uploaded`} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "4px 8px 4px 6px",
                    background: "#fff", border: "1px dashed var(--outline-v)",
                    borderRadius: 20, flexShrink: 0, maxWidth: 200,
                  }}>
                    {isImg ? (
                      /* eslint-disable-next-line @next/next/no-img-element */
                      <img src={URL.createObjectURL(file)} alt={file.name}
                        style={{ width: 20, height: 20, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }} />
                    ) : (
                      <div style={{ width: 20, height: 20, borderRadius: "50%", background: meta.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <i className={`ti ${meta.icon}`} style={{ fontSize: 11, color: meta.color }} />
                      </div>
                    )}
                    <span style={{ fontSize: 11, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 110 }}>
                      {file.name}
                    </span>
                    <i className="ti ti-upload" style={{ fontSize: 10, color: "var(--primary)", flexShrink: 0 }} title="New — will be uploaded" />
                    <button type="button" suppressHydrationWarning
                      onClick={() => removeFile(i)}
                      style={{ background: "none", border: "none", cursor: "pointer", padding: 0, lineHeight: 1, color: "var(--outline)", flexShrink: 0 }}
                      onMouseEnter={e => (e.currentTarget.style.color = "var(--error)")}
                      onMouseLeave={e => (e.currentTarget.style.color = "var(--outline)")}>
                      <i className="ti ti-x" style={{ fontSize: 11 }} />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {(existingAttachments.length + form.attachments.length) > 0 && (
            <span style={{ fontSize: 11, color: "var(--outline)", flexShrink: 0, marginLeft: "auto", whiteSpace: "nowrap" }}>
              {existingAttachments.length + form.attachments.length} file{(existingAttachments.length + form.attachments.length) !== 1 ? "s" : ""}
              {form.attachments.length > 0 && <span style={{ color: "var(--primary)" }}> · {form.attachments.length} new</span>}
            </span>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer" style={{ flexShrink: 0 }}>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> {isAddMode ? "Create Template" : "Save Template"}</>
            }
          </button>
        </div>

        <style>{`
          [contenteditable]:focus { border-color: var(--primary) !important; }
          [contenteditable] img { max-width: 100%; height: auto; cursor: pointer; border-radius: 4px; transition: outline 0.1s; }
          [contenteditable] img:hover { outline: 2px solid rgba(30,78,140,0.4); }
          [contenteditable] img:focus { outline: 2px solid var(--primary); }
          @keyframes spin { to { transform: rotate(360deg); } }

          /* ── Responsive modal ── */

          /* Tablet (641px–1023px): editor + sidebar only, no preview */
          @media (min-width: 641px) and (max-width: 1023px) {
            .et-modal-grid { grid-template-columns: 1fr 200px !important; }
            .et-col-preview { display: none !important; }
            .et-tab-bar { display: none !important; }
          }

          /* Mobile (≤640px): full-screen, tab-switched single column */
          @media (max-width: 640px) {
            .et-modal-wrap {
              width: 100vw !important;
              max-width: 100vw !important;
              height: 100dvh !important;
              max-height: 100dvh !important;
              border-radius: 0 !important;
            }
            .et-tab-bar { display: flex !important; }
            .et-modal-grid { grid-template-columns: 1fr !important; }
            .et-col-editor,
            .et-col-preview,
            .et-col-sidebar { display: none !important; }
            .et-col-editor.et-tab-active  { display: flex !important; flex-direction: column; overflow: hidden; }
            .et-col-preview.et-tab-active { display: flex !important; flex-direction: column; overflow-y: auto; }
            .et-col-sidebar.et-tab-active { display: block !important; overflow-y: auto; }
          }
        `}</style>
      </div>
    </div>

    {/* ── Crop modal ── */}
    {cropState && (
      <div style={{ position: "fixed", inset: 0, zIndex: 10001, background: "rgba(0,0,0,0.82)", display: "flex", alignItems: "center", justifyContent: "center" }}
        onClick={e => { if (e.target === e.currentTarget) setCropState(null); }}>
        <div style={{ background: "#fff", borderRadius: 12, overflow: "hidden", boxShadow: "0 24px 64px rgba(0,0,0,0.5)", maxWidth: "96vw" }}>

          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", borderBottom: "1px solid var(--outline-v)" }}>
            <i className="ti ti-crop" style={{ fontSize: 16, color: "var(--primary)" }} />
            <span style={{ fontWeight: 600, fontSize: 14 }}>Crop Image</span>
            <span style={{ fontSize: 12, color: "var(--on-variant)", marginLeft: 4 }}>— drag to select area</span>
            <button type="button" onClick={() => setCropState(null)} suppressHydrationWarning
              style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", fontSize: 18, color: "var(--outline)", lineHeight: 1 }}>
              <i className="ti ti-x" />
            </button>
          </div>

          {/* Canvas area */}
          <div style={{ padding: 16, background: "#111", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <div
              style={{ position: "relative", width: cropState.dispW, height: cropState.dispH, cursor: "crosshair", userSelect: "none", flexShrink: 0 }}
              onMouseDown={cropDown} onMouseMove={cropMove} onMouseUp={cropUp} onMouseLeave={cropUp}>

              {/* Base image */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={cropState.src} alt="crop" draggable={false}
                style={{ display: "block", width: cropState.dispW, height: cropState.dispH, pointerEvents: "none" }} />

              {/* Selection rectangle */}
              {cropState.sel.w > 2 && cropState.sel.h > 2 && (
                <div style={{
                  position: "absolute",
                  left: cropState.sel.x, top: cropState.sel.y,
                  width: cropState.sel.w, height: cropState.sel.h,
                  border: "2px dashed #fff",
                  outline: "1px solid rgba(0,0,0,0.5)",
                  pointerEvents: "none",
                  boxSizing: "border-box",
                }} />
              )}
            </div>
          </div>

          {/* Selection info */}
          <div style={{ padding: "8px 18px", background: "var(--bg-low)", borderTop: "1px solid var(--outline-v)", fontSize: 12, color: "var(--on-variant)" }}>
            {cropState.sel.w > 2 && cropState.sel.h > 2
              ? `Selection: ${Math.round(cropState.sel.w)} × ${Math.round(cropState.sel.h)} px`
              : "Drag on the image to select the crop area"}
          </div>

          {/* Footer */}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", padding: "12px 18px", borderTop: "1px solid var(--outline-v)" }}>
            <button className="btn btn-ghost" type="button" onClick={() => setCropState(null)} suppressHydrationWarning>Cancel</button>
            <button className="btn btn-filled" type="button" onClick={applyCrop} suppressHydrationWarning
              disabled={cropState.sel.w < 4 || cropState.sel.h < 4}>
              <i className="ti ti-check" /> Apply Crop
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
