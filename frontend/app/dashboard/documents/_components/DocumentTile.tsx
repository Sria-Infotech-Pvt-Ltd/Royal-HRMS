"use client";

import { CATEGORY_META, formatUploadedAt, getFileTypeMeta, type ApiDocument } from "../_data";

export default function DocumentTile({ doc, onOpen }: { doc: ApiDocument; onOpen: (doc: ApiDocument) => void }) {
  const fm = getFileTypeMeta(doc.file_type);
  const cm = CATEGORY_META[doc.category] ?? CATEGORY_META.other;

  return (
    <div className="doc-tile" onClick={() => onOpen(doc)}>
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
}
