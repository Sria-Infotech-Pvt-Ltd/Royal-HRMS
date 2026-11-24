"use client";

import { CATEGORY_META, formatUploadedAt, getFileTypeMeta, type ApiDocument } from "../_data";
import { isNewDocument } from "../_view";
import { useT } from "@/hooks/useI18n";

export default function DocumentTile({ doc, onOpen }: { doc: ApiDocument; onOpen: (doc: ApiDocument) => void }) {
  const t = useT();
  const fm = getFileTypeMeta(doc.file_type);
  const cm = CATEGORY_META[doc.category] ?? CATEGORY_META.other;

  return (
    <div className="doc-tile" onClick={() => onOpen(doc)}>
      {/* Icon */}
      <div className="dx-tile-top">
        <div className={`doc-icon ${fm.iconClass}`}>
          <i className={`ti ${fm.icon}`} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {isNewDocument(doc) && <span className="dx-new">{t("NEW")}</span>}
          <div className="dx-quick" onClick={event => event.stopPropagation()}>
            <a href={doc.file_url} download={doc.file_name} title={t("Download")} aria-label={t("Download {title}", { title: doc.title })}><i className="ti ti-download" /></a>
          </div>
        </div>
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
        {t("Uploaded {date}", { date: formatUploadedAt(doc.uploaded_at) })}
      </div>
      <div style={{ fontSize: 11, color: "var(--outline)" }}>
        {t("by {name}", { name: doc.uploaded_by_name })}
      </div>

      {/* Category badge */}
      <div style={{ marginTop: 4 }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 10, background: cm.bg, color: cm.color, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <i className={`ti ${cm.icon}`} style={{ fontSize: 10 }} />
          {t(cm.label)}
        </span>
      </div>
    </div>
  );
}
