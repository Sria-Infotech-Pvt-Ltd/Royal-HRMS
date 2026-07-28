"use client";

import { useEffect, useRef, useState } from "react";
import type { ApiDocument } from "../_data";
import { getFileTypeMeta } from "../_data";

interface Props {
  doc:        ApiDocument;
  blobUrl:    string | null;  // for PDF / image
  textContent: string | null; // for TXT / CSV
  loading:    boolean;
  error:      string | null;
}

// ─── DOCX renderer ────────────────────────────────────────────────────────────

function DocxPreview({ fileUrl }: { fileUrl: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function render() {
      try {
        // Dynamic import — avoids SSR crash (docx-preview uses browser APIs)
        const { renderAsync } = await import("docx-preview");
        // No auth header — files are on MinIO (object storage), not Django API
        const res = await fetch(fileUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf = await res.arrayBuffer();
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = "";
        await renderAsync(buf, containerRef.current, undefined, {
          className:                   "docx-preview",
          ignoreWidth:                 false,
          ignoreHeight:                true,
          ignoreFonts:                 false,
          breakPages:                  true,
          ignoreLastRenderedPageBreak: true,
          useBase64URL:                true,
          renderChanges:               false,
          renderHeaders:               true,
          renderFooters:               true,
          renderFootnotes:             true,
          renderEndnotes:              true,
        });
      } catch (e: unknown) {
        if (!cancelled) setErr((e as { message?: string }).message ?? "Render failed");
      }
    }
    render();
    return () => { cancelled = true; };
  }, [fileUrl]);

  if (err) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 32, color: "var(--on-variant)", flexDirection: "column", gap: 8 }}>
      <i className="ti ti-file-off" style={{ fontSize: 32, opacity: 0.3 }} />
      <span style={{ fontSize: 13 }}>Could not render document — {err}</span>
    </div>
  );

  return (
    <div style={{ flex: 1, overflowY: "auto", background: "#e8eaed", padding: "20px 0" }}>
      <div ref={containerRef} style={{ maxWidth: 820, margin: "0 auto" }} />
      <style>{`
        .docx-preview { background: #fff; padding: 60px 72px; box-shadow: 0 1px 6px rgba(0,0,0,0.12); font-family: "Calibri", "Times New Roman", serif; }
        .docx-preview section { margin-bottom: 0 !important; }
        @media (max-width: 640px) { .docx-preview { padding: 28px 20px; } }
      `}</style>
    </div>
  );
}

// ─── XLSX / XLS renderer ──────────────────────────────────────────────────────

function XlsxPreview({ fileUrl }: { fileUrl: string }) {
  const [html,    setHtml]    = useState<string | null>(null);
  const [sheets,  setSheets]  = useState<string[]>([]);
  const [active,  setActive]  = useState(0);
  const [allHtml, setAllHtml] = useState<string[]>([]);
  const [err,     setErr]     = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function render() {
      try {
        const XLSX = await import("xlsx");
        const res  = await fetch(fileUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const buf  = await res.arrayBuffer();
        if (cancelled) return;
        const wb   = XLSX.read(buf, { type: "array" });
        const htmlArr = wb.SheetNames.map(name => {
          const ws = wb.Sheets[name];
          // sheet_to_html() throws internally when a sheet has no data (no "!ref" range) —
          // render an empty-sheet placeholder instead of failing the whole preview.
          if (!ws || !ws["!ref"]) {
            return '<div style="padding:16px;color:#9aa0a6;font-size:12px;">This sheet is empty.</div>';
          }
          return XLSX.utils.sheet_to_html(ws, { editable: false });
        });
        if (cancelled) return;
        setSheets(wb.SheetNames);
        setAllHtml(htmlArr);
        setHtml(htmlArr[0] ?? "");
      } catch (e: unknown) {
        if (!cancelled) setErr((e as { message?: string }).message ?? "Render failed");
      }
    }
    render();
    return () => { cancelled = true; };
  }, [fileUrl]);

  if (err) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: 32, color: "var(--on-variant)", flexDirection: "column", gap: 8 }}>
      <i className="ti ti-file-off" style={{ fontSize: 32, opacity: 0.3 }} />
      <span style={{ fontSize: 13 }}>Could not render spreadsheet — {err}</span>
    </div>
  );

  if (!html) return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 10, color: "var(--on-variant)" }}>
      <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "dcSpin 1s linear infinite" }} />
      <span style={{ fontSize: 13 }}>Parsing spreadsheet…</span>
    </div>
  );

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
      {/* Sheet tabs */}
      {sheets.length > 1 && (
        <div style={{ display: "flex", gap: 2, padding: "8px 16px 0", background: "#fff", borderBottom: "1px solid var(--outline-v)", flexShrink: 0, overflowX: "auto" }}>
          {sheets.map((name, i) => (
            <button key={name} type="button" suppressHydrationWarning
              onClick={() => { setActive(i); setHtml(allHtml[i]); }}
              style={{ padding: "6px 14px", fontSize: 12, fontFamily: "inherit", border: "none", borderBottom: `2px solid ${active === i ? "var(--primary)" : "transparent"}`, background: "none", cursor: "pointer", color: active === i ? "var(--primary)" : "var(--on-variant)", fontWeight: active === i ? 600 : 400, whiteSpace: "nowrap" }}>
              {name}
            </button>
          ))}
        </div>
      )}
      {/* Table */}
      <div style={{ flex: 1, overflowY: "auto", overflowX: "auto", padding: 16, background: "#fafbfc" }}>
        <div dangerouslySetInnerHTML={{ __html: html }} />
        <style>{`
          .xl-preview table { border-collapse: collapse; font-size: 12px; font-family: "Calibri", sans-serif; }
          table td, table th { border: 1px solid #d3dae8; padding: 4px 10px; min-width: 60px; white-space: nowrap; }
          table th { background: #e7ecf4; font-weight: 600; }
          table tr:nth-child(even) td { background: #f7f9fc; }
        `}</style>
      </div>
    </div>
  );
}

// ─── Main export ──────────────────────────────────────────────────────────────

export default function DocPreviewBody({ doc, blobUrl, textContent, loading, error }: Props) {
  const ft = doc.file_type.toUpperCase();
  const fm = getFileTypeMeta(doc.file_type);

  // Loading spinner
  if (loading) return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, color: "var(--on-variant)" }}>
      <i className="ti ti-loader-2" style={{ fontSize: 32, animation: "dcSpin 1s linear infinite" }} />
      <span style={{ fontSize: 13 }}>Loading preview…</span>
    </div>
  );

  // Fetch error
  if (error) return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 14, padding: 32 }}>
      <i className="ti ti-file-off" style={{ fontSize: 40, opacity: 0.25, color: "var(--on-variant)" }} />
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)" }}>Preview unavailable</div>
      <div style={{ fontSize: 12, color: "var(--outline)" }}>{error}</div>
    </div>
  );

  // PDF — blob URL in iframe
  // #toolbar=0&navpanes=0 suppresses the browser's native PDF toolbar and
  // side panel (Chrome/Edge); Firefox uses PDF.js which ignores these params
  // but also shows a minimal UI by default.
  if (ft === "PDF" && blobUrl) return (
    <iframe
      src={`${blobUrl}#toolbar=0&navpanes=0&view=FitH`}
      title={doc.title}
      style={{ flex: 1, width: "100%", border: "none", display: "block" }}
    />
  );

  // Images — blob URL in img
  if (["JPG", "PNG"].includes(ft) && blobUrl) return (
    <div style={{ flex: 1, overflow: "auto", display: "flex", alignItems: "center", justifyContent: "center", padding: 24, background: "#e8eaed" }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={blobUrl} alt={doc.title}
        style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain", borderRadius: "var(--radius)", boxShadow: "var(--shadow-md)" }} />
    </div>
  );

  // TXT / CSV — pre block
  if (textContent !== null) return (
    <div style={{ flex: 1, overflow: "auto", padding: 24, background: "#fff" }}>
      <pre style={{ margin: 0, fontSize: 12, lineHeight: 1.7, color: "var(--on-bg)", fontFamily: "ui-monospace, monospace", whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
        {textContent}
      </pre>
    </div>
  );

  // DOCX — rendered with docx-preview
  if (["DOCX", "DOC"].includes(ft)) return <DocxPreview fileUrl={doc.file_url} />;

  // XLSX / XLS / CSV — rendered with SheetJS
  if (["XLSX", "XLS"].includes(ft)) return <XlsxPreview fileUrl={doc.file_url} />;

  // PPT / PPTX — no client-side renderer; show download prompt
  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, padding: 32 }}>
      <div className={`doc-icon ${fm.iconClass}`} style={{ width: 64, height: 64, fontSize: 30 }}>
        <i className={`ti ${fm.icon}`} />
      </div>
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: 15, fontWeight: 600, color: "var(--on-bg)", marginBottom: 6 }}>{doc.title}</div>
        <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 4 }}>{doc.file_type} · {doc.file_size_display}</div>
        <div style={{ fontSize: 12, color: "var(--outline)" }}>
          In-browser preview is not available for {doc.file_type} files.
        </div>
      </div>
      <a href={doc.file_url} download={doc.file_name} className="btn btn-filled" suppressHydrationWarning>
        <i className="ti ti-download" /> Download to view
      </a>
    </div>
  );
}
