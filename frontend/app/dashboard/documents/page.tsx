"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import DocPreviewBody from "./_components/DocPreviewBody";
import {
  DOCUMENTS_BASE, DOCUMENTS_STATS, documentDetail,
  CATEGORY_META, DOC_ACCEPT, EMPTY_UPLOAD_FORM, formatUploadedAt,
  getFileTypeMeta, validateUploadForm,
  type ApiDocument, type ApiStatsResponse, type DocCategory,
  type DocUploadErrors, type DocUploadForm,
} from "./_data";

// ─── Filter tabs ──────────────────────────────────────────────────────────────

const FILTERS = ["All Documents", "Policies", "Forms", "Templates"] as const;
type Filter = typeof FILTERS[number];

const FILTER_TO_CATEGORY: Record<Filter, DocCategory | ""> = {
  "All Documents": "",
  "Policies":      "policy",
  "Forms":         "form",
  "Templates":     "template",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DocumentCenterPage() {
  // ── Data state ─────────────────────────────────────────────────────────────
  const [documents,    setDocuments]    = useState<ApiDocument[]>([]);
  const [stats,        setStats]        = useState<ApiStatsResponse | null>(null);
  const [loading,      setLoading]      = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [error,        setError]        = useState<string | null>(null);

  // ── UI state ───────────────────────────────────────────────────────────────
  const [filter,       setFilter]       = useState<Filter>("All Documents");
  const [search,       setSearch]       = useState("");
  const [debouncedQ,   setDebouncedQ]   = useState("");
  const [selected,     setSelected]     = useState<ApiDocument | null>(null);
  const [showUpload,   setShowUpload]   = useState(false);
  const [uploadForm,   setUploadForm]   = useState<DocUploadForm>(EMPTY_UPLOAD_FORM);
  const [uploadErrors, setUploadErrors] = useState<DocUploadErrors>({});
  const [uploading,    setUploading]    = useState(false);
  const [deleting,     setDeleting]     = useState(false);
  const [dragOver,     setDragOver]     = useState(false);
  const [toast,        setToast]        = useState<{ msg: string; ok: boolean } | null>(null);

  // ── Preview state ──────────────────────────────────────────────────────────
  const [previewDoc,     setPreviewDoc]     = useState<ApiDocument | null>(null);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);
  const [previewText,    setPreviewText]    = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError,   setPreviewError]   = useState<string | null>(null);
  const blobUrlRef = useRef<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Toast ──────────────────────────────────────────────────────────────────
  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3200);
  }

  // ── Debounce search ────────────────────────────────────────────────────────
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => setDebouncedQ(search), 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [search]);

  // ── Fetch stats ────────────────────────────────────────────────────────────
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await clientApi.get(DOCUMENTS_STATS);
      setStats(res.data.data ?? res.data);
    } catch {
      // stats failure is non-critical; counts fall back to list length
    } finally {
      setStatsLoading(false);
    }
  }, []);

  // ── Fetch documents ────────────────────────────────────────────────────────
  const loadDocuments = useCallback(async (category: string, q: string) => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = {};
      if (category) params.category = category;
      if (q.trim()) params.search   = q.trim();
      const res = await clientApi.get(DOCUMENTS_BASE, { params });
      const envelope = res.data.data ?? res.data;
      const data = Array.isArray(envelope) ? envelope : (envelope?.results ?? []);
      setDocuments(data);
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadStats(); }, [loadStats]);

  useEffect(() => {
    loadDocuments(FILTER_TO_CATEGORY[filter], debouncedQ);
  }, [filter, debouncedQ, loadDocuments]);

  // ── Derived counts ─────────────────────────────────────────────────────────
  const total         = stats?.total                      ?? documents.length;
  const policyCount   = stats?.by_category?.policy        ?? 0;
  const formCount     = stats?.by_category?.form          ?? 0;
  const templateCount = stats?.by_category?.template      ?? 0;

  // ── Upload ─────────────────────────────────────────────────────────────────
  function handleFileDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      setUploadForm(p => ({ ...p, file, title: p.title || file.name.replace(/\.[^/.]+$/, "") }));
      setUploadErrors(p => ({ ...p, file: undefined }));
    }
  }

  async function handleUpload() {
    const errs = validateUploadForm(uploadForm);
    if (Object.keys(errs).length) { setUploadErrors(errs); return; }

    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("title",    uploadForm.title.trim());
      fd.append("category", uploadForm.category);
      if (uploadForm.description.trim()) fd.append("description", uploadForm.description.trim());
      fd.append("file", uploadForm.file!);

      const res = await clientApi.post(DOCUMENTS_BASE, fd);
      const created: ApiDocument = res.data.data ?? res.data;
      setDocuments(prev => [created, ...prev]);
      setShowUpload(false);
      setUploadForm(EMPTY_UPLOAD_FORM);
      setUploadErrors({});
      showToast("Document uploaded successfully");
      loadStats();
    } catch (err: unknown) {
      const e = err as { message?: string; status?: number };
      if (e.status === 403) {
        showToast("You do not have permission to upload documents.", false);
      } else {
        showToast(e.message ?? "Upload failed. Please try again.", false);
      }
    } finally {
      setUploading(false);
    }
  }

  // ── Delete ─────────────────────────────────────────────────────────────────
  async function handleDelete(doc: ApiDocument) {
    if (!confirm(`Delete "${doc.title}"? This cannot be undone.`)) return;
    setDeleting(true);
    try {
      await clientApi.delete(documentDetail(doc.id));
      setDocuments(prev => prev.filter(d => d.id !== doc.id));
      setSelected(null);
      showToast(`"${doc.title}" deleted`);
      loadStats();
    } catch (err: unknown) {
      const e = err as { message?: string; status?: number };
      if (e.status === 403) {
        showToast("You do not have permission to delete documents.", false);
      } else {
        showToast(e.message ?? "Delete failed.", false);
      }
    } finally {
      setDeleting(false);
    }
  }

  // ── Close upload modal ─────────────────────────────────────────────────────
  function closeUpload() {
    setShowUpload(false);
    setUploadForm(EMPTY_UPLOAD_FORM);
    setUploadErrors({});
  }

  // ── Preview ────────────────────────────────────────────────────────────────
  async function openPreview(doc: ApiDocument) {
    setPreviewDoc(doc);
    setPreviewBlobUrl(null);
    setPreviewText(null);
    setPreviewError(null);
    setPreviewLoading(true);

    // Revoke previous blob URL to free memory
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null; }

    const ft = doc.file_type.toUpperCase();

    // Media files are served directly from MinIO (object storage).
    // MinIO uses its own bucket-level access policy — sending the Django
    // JWT Bearer token causes MinIO to return 401. Fetch without auth headers.
    async function fetchMedia(url: string): Promise<Response> {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res;
    }

    try {
      if (["JPG", "PNG"].includes(ft)) {
        const res  = await fetchMedia(doc.file_url);
        const blob = await res.blob();
        const url  = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setPreviewBlobUrl(url);

      } else if (ft === "PDF") {
        // Fetch as blob → object URL so the browser renders inline
        // (ignores Content-Disposition: attachment from the server)
        const res  = await fetchMedia(doc.file_url);
        const blob = new Blob([await res.arrayBuffer()], { type: "application/pdf" });
        const url  = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setPreviewBlobUrl(url);

      } else if (["TXT", "CSV"].includes(ft)) {
        const res = await fetchMedia(doc.file_url);
        setPreviewText(await res.text());

      }
    } catch (err: unknown) {
      setPreviewError((err as { message?: string }).message ?? "Failed to load preview.");
    } finally {
      setPreviewLoading(false);
    }
  }

  function closePreview() {
    setPreviewDoc(null);
    setPreviewBlobUrl(null);
    setPreviewText(null);
    setPreviewError(null);
    if (blobUrlRef.current) { URL.revokeObjectURL(blobUrlRef.current); blobUrlRef.current = null; }
  }

  return (
    <>
      {/* Toast */}
      {toast && (
        <div className="dc-toast" style={{ position: "fixed", top: 16, right: 20, zIndex: 9999, display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", background: toast.ok ? "var(--success-c)" : "var(--error-c)", border: `1px solid ${toast.ok ? "var(--success)" : "var(--error)"}`, borderRadius: "var(--radius)", boxShadow: "var(--shadow-md)", fontSize: 13, color: toast.ok ? "var(--success)" : "var(--error)", animation: "dcSlideIn 0.2s ease", maxWidth: "calc(100vw - 40px)" }}>
          <i className={`ti ${toast.ok ? "ti-circle-check" : "ti-alert-circle"}`} style={{ fontSize: 16, flexShrink: 0 }} />
          {toast.msg}
        </div>
      )}

      {/* Page header */}
      <div className="page-header" style={{ flexWrap: "wrap", gap: 10 }}>
        <div>
          <div className="page-title">Document Center</div>
          <div className="page-sub">Policies, forms, and templates — all in one place</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowUpload(true)} suppressHydrationWarning>
            <i className="ti ti-upload" /> Upload Document
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div className="dc-stats-row" style={{ display: "grid", gap: 12, marginBottom: 24 }}>
        {([
          { label: "Total Documents", value: statsLoading ? "—" : total,         icon: "ti-copy",             color: "var(--primary)", bg: "rgba(30,78,140,0.08)"  },
          { label: "Policies",        value: statsLoading ? "—" : policyCount,   icon: "ti-shield-check",     color: "#c28b00",        bg: "rgba(194,139,0,0.10)"  },
          { label: "Forms",           value: statsLoading ? "—" : formCount,     icon: "ti-file-description", color: "var(--info)",    bg: "rgba(14,124,134,0.10)" },
          { label: "Templates",       value: statsLoading ? "—" : templateCount, icon: "ti-table",            color: "var(--success)", bg: "rgba(27,138,107,0.10)" },
        ] as const).map(stat => (
          <div key={stat.label} style={{ background: "#fff", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>{stat.label}</div>
              <div style={{ fontSize: 26, fontWeight: 700, color: "var(--on-bg)", lineHeight: 1 }}>{stat.value}</div>
            </div>
            <div style={{ width: 44, height: 44, borderRadius: 10, background: stat.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <i className={`ti ${stat.icon}`} style={{ fontSize: 20, color: stat.color }} />
            </div>
          </div>
        ))}
      </div>

      {/* Filter tabs + search */}
      <div className="dc-toolbar" style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {FILTERS.map(f => (
            <button key={f} type="button" suppressHydrationWarning
              onClick={() => setFilter(f)}
              style={{
                padding: "7px 16px", borderRadius: 20, border: "1.5px solid",
                borderColor: filter === f ? "var(--primary)" : "var(--outline-v)",
                background:  filter === f ? "var(--primary)" : "#fff",
                color:       filter === f ? "#fff" : "var(--on-variant)",
                fontSize: 13, fontWeight: filter === f ? 600 : 400,
                cursor: "pointer", fontFamily: "inherit", transition: "all 0.15s",
              }}>
              {f}
            </button>
          ))}
        </div>
        <div style={{ position: "relative", marginLeft: "auto" }} className="dc-search-wrap">
          <i className="ti ti-search" style={{ position: "absolute", left: 11, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "var(--outline)", pointerEvents: "none" }} />
          <input className="field-input" placeholder="Search documents…" value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ paddingLeft: 34, width: 220 }} suppressHydrationWarning />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 200, gap: 10, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "dcSpin 1s linear infinite" }} /> Loading documents…
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>Failed to load</strong> — {error}
            <div style={{ marginTop: 8 }}>
              <button className="btn btn-ghost btn-sm" onClick={() => loadDocuments(FILTER_TO_CATEGORY[filter], debouncedQ)} suppressHydrationWarning>
                Retry
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && documents.length === 0 && (
        <div style={{ textAlign: "center", padding: "52px 0", color: "var(--on-variant)" }}>
          <i className="ti ti-folder-off" style={{ fontSize: 40, opacity: 0.25, display: "block", marginBottom: 12 }} />
          <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>No documents found</div>
          {(search || filter !== "All Documents") && (
            <div style={{ fontSize: 13, color: "var(--outline)" }}>
              Try a different filter or search term
            </div>
          )}
        </div>
      )}

      {/* Document grid */}
      {!loading && !error && documents.length > 0 && (
        <div className="doc-grid">
          {documents.map(doc => {
            const fm = getFileTypeMeta(doc.file_type);
            const cm = CATEGORY_META[doc.category] ?? CATEGORY_META.other;
            return (
              <div key={doc.id} className="doc-tile" onClick={() => setSelected(doc)}>
                {/* Icon */}
                <div className={`doc-icon ${fm.iconClass}`}>
                  <i className={`ti ${fm.icon}`} />
                </div>

                {/* Name */}
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", lineHeight: 1.4, wordBreak: "break-word" }}>
                  {doc.title}
                </div>

                {/* Type + size */}
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                  {fm.label} · {doc.file_size_display}
                </div>

                {/* Date + uploader */}
                <div style={{ fontSize: 11, color: "var(--outline)", marginTop: 2 }}>
                  Uploaded {formatUploadedAt(doc.uploaded_at)}
                </div>
                <div style={{ fontSize: 11, color: "var(--outline)" }}>
                  by {doc.uploaded_by_name}
                </div>

                {/* Category badge */}
                <div style={{ marginTop: 4 }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 10, background: cm.bg, color: cm.color, textTransform: "uppercase", letterSpacing: "0.05em" }}>
                    <i className={`ti ${cm.icon}`} style={{ fontSize: 10 }} />
                    {cm.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Document detail modal ── */}
      {selected && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) setSelected(null); }}>
          <div className="modal" style={{ width: "min(560px, 96vw)", maxHeight: "90vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>

            <div className="modal-header" style={{ flexShrink: 0 }}>
              <div style={{ minWidth: 0 }}>
                <div className="modal-title" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selected.title}
                </div>
              </div>
              <button className="modal-close" onClick={() => setSelected(null)} suppressHydrationWarning>
                <i className="ti ti-x" />
              </button>
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: "auto" }}>
              {/* File preview banner */}
              {(() => {
                const fm = getFileTypeMeta(selected.file_type);
                return (
                  <div style={{ background: "var(--bg-low)", borderRadius: "var(--radius)", padding: "32px 24px", textAlign: "center", marginBottom: 20 }}>
                    <div className={`doc-icon ${fm.iconClass}`} style={{ width: 56, height: 56, fontSize: 26, margin: "0 auto 12px" }}>
                      <i className={`ti ${fm.icon}`} />
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginBottom: 4 }}>{selected.title}</div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                      {fm.label} · {selected.file_size_display}
                    </div>
                  </div>
                );
              })()}

              {/* Metadata rows */}
              {([
                { label: "Category",    value: selected.category_display },
                { label: "Uploaded by", value: selected.uploaded_by_name },
                { label: "Upload date", value: formatUploadedAt(selected.uploaded_at) },
                { label: "Access",      value: selected.branch_name ? `Branch: ${selected.branch_name}` : "All Employees" },
                ...(selected.branch_name ? [] : []),
              ]).map(row => (
                <div key={row.label} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-v)" }}>
                  <span style={{ fontSize: 13, color: "var(--on-variant)" }}>{row.label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{row.value}</span>
                </div>
              ))}

              {selected.description && (
                <div style={{ marginTop: 16, padding: 14, background: "var(--bg-low)", borderRadius: "var(--radius)", fontSize: 13, color: "var(--on-variant)", lineHeight: 1.6 }}>
                  {selected.description}
                </div>
              )}
            </div>

            <div className="modal-footer" style={{ flexShrink: 0 }}>
              <button className="btn btn-danger btn-sm" onClick={() => handleDelete(selected)} disabled={deleting} suppressHydrationWarning>
                {deleting
                  ? <><i className="ti ti-loader-2" style={{ animation: "dcSpin 1s linear infinite" }} /> Deleting…</>
                  : <><i className="ti ti-trash" /> Delete</>
                }
              </button>
              <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                <button className="btn btn-ghost" onClick={() => setSelected(null)} suppressHydrationWarning>Close</button>
                <button className="btn btn-outline btn-sm"
                  onClick={() => openPreview(selected)}
                  suppressHydrationWarning>
                  <i className="ti ti-eye" /> Preview
                </button>
                <button className="btn btn-filled"
                  onClick={() => {
                    const a = document.createElement("a");
                    a.href = selected.file_url;
                    a.download = selected.file_name;
                    a.click();
                  }}
                  suppressHydrationWarning>
                  <i className="ti ti-download" /> Download
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Preview modal ── */}
      {previewDoc && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) closePreview(); }}>
          <div className="modal" style={{ width: "min(1100px, 97vw)", height: "94vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>

            {/* Header */}
            <div className="modal-header" style={{ flexShrink: 0 }}>
              <div style={{ minWidth: 0, display: "flex", alignItems: "center", gap: 10 }}>
                <div className={`doc-icon ${getFileTypeMeta(previewDoc.file_type).iconClass}`} style={{ width: 30, height: 30, fontSize: 15, flexShrink: 0 }}>
                  <i className={`ti ${getFileTypeMeta(previewDoc.file_type).icon}`} />
                </div>
                <div style={{ minWidth: 0 }}>
                  <div className="modal-title" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {previewDoc.title}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 1 }}>
                    {previewDoc.file_type} · {previewDoc.file_size_display}
                  </div>
                </div>
              </div>
              <button className="modal-close" onClick={closePreview} suppressHydrationWarning>
                <i className="ti ti-x" />
              </button>
            </div>

            {/* Preview body */}
            <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <DocPreviewBody
                doc={previewDoc}
                blobUrl={previewBlobUrl}
                textContent={previewText}
                loading={previewLoading}
                error={previewError}
              />
            </div>

            {/* Footer */}
            <div className="modal-footer" style={{ flexShrink: 0 }}>
              <button className="btn btn-ghost" onClick={closePreview} suppressHydrationWarning>Close</button>
              <button className="btn btn-filled"
                onClick={() => {
                  const a = document.createElement("a");
                  a.href     = previewBlobUrl ?? previewDoc.file_url;
                  a.download = previewDoc.file_name;
                  a.click();
                }}
                suppressHydrationWarning>
                <i className="ti ti-download" /> Download
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Upload modal ── */}
      {showUpload && (
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) closeUpload(); }}>
          <div className="modal" style={{ width: "min(520px, 96vw)", maxHeight: "90vh", display: "flex", flexDirection: "column", overflow: "hidden" }}>

            <div className="modal-header" style={{ flexShrink: 0 }}>
              <div>
                <div className="modal-title">Upload Document</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>PDF, Word, Excel, PPT, images, TXT, CSV — up to 25 MB</div>
              </div>
              <button className="modal-close" onClick={closeUpload} suppressHydrationWarning>
                <i className="ti ti-x" />
              </button>
            </div>

            <div className="modal-body" style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 }}>

              {/* Drop zone */}
              <div
                onDragOver={e => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => document.getElementById("dc-file-input")?.click()}
                style={{
                  border: `2px dashed ${dragOver ? "var(--primary)" : uploadErrors.file ? "var(--error)" : "var(--outline-v)"}`,
                  borderRadius: "var(--radius)",
                  background: dragOver ? "rgba(30,78,140,0.04)" : "var(--bg-low)",
                  padding: "28px 16px",
                  textAlign: "center",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}>
                <input id="dc-file-input" type="file" accept={DOC_ACCEPT} style={{ display: "none" }}
                  onChange={e => {
                    const file = e.target.files?.[0];
                    if (file) {
                      setUploadForm(p => ({
                        ...p, file,
                        title: p.title || file.name.replace(/\.[^/.]+$/, "").replace(/[-_]/g, " "),
                      }));
                      setUploadErrors(p => ({ ...p, file: undefined }));
                    }
                    e.target.value = "";
                  }} suppressHydrationWarning />
                {uploadForm.file ? (
                  <>
                    <i className="ti ti-circle-check" style={{ fontSize: 28, color: "var(--success)", display: "block", marginBottom: 8 }} />
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{uploadForm.file.name}</div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                      {uploadForm.file.size < 1024 * 1024
                        ? `${(uploadForm.file.size / 1024).toFixed(0)} KB`
                        : `${(uploadForm.file.size / (1024 * 1024)).toFixed(1)} MB`
                      } — click to change
                    </div>
                  </>
                ) : (
                  <>
                    <i className="ti ti-cloud-upload" style={{ fontSize: 32, color: "var(--outline)", display: "block", marginBottom: 8 }} />
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>Drop a file here or click to browse</div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>PDF, Word, Excel, PPT, images, TXT, CSV</div>
                  </>
                )}
              </div>
              {uploadErrors.file && <span className="field-error">{uploadErrors.file}</span>}

              {/* Document name */}
              <div className="field-group">
                <label className="field-label">Document Name <span style={{ color: "var(--error)" }}>*</span></label>
                <input className="field-input" placeholder="e.g. Employee Handbook 2025"
                  value={uploadForm.title}
                  onChange={e => { setUploadForm(p => ({ ...p, title: e.target.value })); setUploadErrors(p => ({ ...p, title: undefined })); }}
                  suppressHydrationWarning />
                {uploadErrors.title && <span className="field-error">{uploadErrors.title}</span>}
              </div>

              {/* Description */}
              <div className="field-group">
                <label className="field-label">Description <span style={{ fontSize: 11, color: "var(--outline)" }}>(optional)</span></label>
                <textarea className="field-input" placeholder="Brief description of this document…" rows={2}
                  value={uploadForm.description}
                  onChange={e => setUploadForm(p => ({ ...p, description: e.target.value }))}
                  style={{ resize: "vertical" }}
                  suppressHydrationWarning />
              </div>

              {/* Category */}
              <div className="field-group">
                <label className="field-label">Category <span style={{ color: "var(--error)" }}>*</span></label>
                <select className="field-input"
                  value={uploadForm.category}
                  onChange={e => { setUploadForm(p => ({ ...p, category: e.target.value as DocCategory | "" })); setUploadErrors(p => ({ ...p, category: undefined })); }}
                  suppressHydrationWarning>
                  <option value="">Select a category…</option>
                  <option value="policy">Policy</option>
                  <option value="form">Form</option>
                  <option value="template">Template</option>
                  <option value="other">Other</option>
                </select>
                {uploadErrors.category && <span className="field-error">{uploadErrors.category}</span>}
              </div>
            </div>

            <div className="modal-footer" style={{ flexShrink: 0 }}>
              <button className="btn btn-ghost" onClick={closeUpload} disabled={uploading} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled" onClick={handleUpload} disabled={uploading} suppressHydrationWarning>
                {uploading
                  ? <><i className="ti ti-loader-2" style={{ animation: "dcSpin 1s linear infinite" }} /> Uploading…</>
                  : <><i className="ti ti-upload" /> Upload Document</>
                }
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes dcSlideIn { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes dcSpin    { to { transform: rotate(360deg); } }

        /* Stats grid */
        .dc-stats-row { grid-template-columns: repeat(4, 1fr); }
        @media (max-width: 900px) { .dc-stats-row { grid-template-columns: 1fr 1fr; } }

        /* Search bar */
        .dc-search-wrap { min-width: 0; }
        @media (max-width: 560px) {
          .dc-search-wrap { width: 100%; }
          .dc-search-wrap input { width: 100% !important; }
          .dc-toolbar { flex-direction: column; align-items: stretch; }
        }

        /* Toast */
        @media (max-width: 480px) {
          .dc-toast { left: 8px !important; right: 8px !important; top: 8px !important; }
        }
      `}</style>
    </>
  );
}
