"use client";

import { CATEGORY_META, formatUploadedAt, getFileTypeMeta, type ApiDocument } from "../_data";
import { isNewDocument } from "../_view";
import { useT } from "@/hooks/useI18n";

/** One document as a list line (the list layout of the Document Center). */
export default function DocumentRow({ doc, onOpen }: { doc: ApiDocument; onOpen: (doc: ApiDocument) => void }) {
  const t = useT();
  const fileType = getFileTypeMeta(doc.file_type);
  const category = CATEGORY_META[doc.category] ?? CATEGORY_META.other;
  return (
    <div className="dx-row" role="button" tabIndex={0} onClick={() => onOpen(doc)} onKeyDown={event => { if (event.key === "Enter") onOpen(doc); }}>
      <div className={`doc-icon ${fileType.iconClass}`}><i className={`ti ${fileType.icon}`} /></div>
      <div className="dx-row-main">
        <div className="dx-row-title">
          <span>{doc.title}</span>
          {isNewDocument(doc) && <span className="dx-new">{t("NEW")}</span>}
        </div>
        <div className="dx-row-meta">{fileType.label} · {doc.file_size_display} · {t("by {name}", { name: doc.uploaded_by_name })}</div>
      </div>
      <div className="dx-row-col">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 10, background: category.bg, color: category.color, textTransform: "uppercase", letterSpacing: "0.05em" }}>
          <i className={`ti ${category.icon}`} /> {t(category.label)}
        </span>
      </div>
      <div className="dx-row-col">{formatUploadedAt(doc.uploaded_at)}</div>
      <div className="dx-quick" onClick={event => event.stopPropagation()}>
        <a href={doc.file_url} download={doc.file_name} title={t("Download")} aria-label={t("Download {title}", { title: doc.title })}><i className="ti ti-download" /></a>
      </div>
    </div>
  );
}
