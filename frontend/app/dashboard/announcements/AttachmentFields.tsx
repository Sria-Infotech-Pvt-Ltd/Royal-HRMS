"use client";

import { useRef, useState, type DragEvent } from "react";
import { useFilePreviews } from "@/hooks/useFilePreviews";
import {
  DOCUMENT_ACCEPT, IMAGE_ACCEPT, LINK_TITLE_MAX, MAX_DOCUMENTS, MAX_IMAGES, MAX_LINKS,
  addFiles, addLink, announcementDownloadHref, documentCount, formatFileSize, imageCount, linkProblems,
  removeExisting, removeLink, removeNew, updateLink,
  type AttachmentDraft, type AttachmentKind,
} from "@/lib/announcementAttachments";

interface Props {
  draft:           AttachmentDraft;
  onChange:        (draft: AttachmentDraft) => void;
  /** Show "required" problems on link rows that are still empty (set after the first save attempt). */
  showLinkErrors?: boolean;
  /** 0-100 while files are being uploaded, null otherwise. */
  uploadProgress?: number | null;
  disabled?:       boolean;
}

const HINT = { fontSize: 12, color: "var(--on-variant)", fontWeight: 400 } as const;
const ROW = { display: "flex", alignItems: "center", gap: 10, padding: "6px 10px", border: "1px solid var(--outline-v)", borderRadius: 8 } as const;

interface TileProps {
  src:      string | null;
  name:     string;
  onRemove: () => void;
  disabled?: boolean;
}

/** One picture in the form: a thumbnail (or an icon until the browser has made one) with a remove button. */
export function ImageTile({ src, name, onRemove, disabled }: TileProps) {
  return (
    <div style={{ position: "relative", width: 72, height: 72, borderRadius: 8, overflow: "hidden", border: "1px solid var(--outline-v)", background: "var(--surface-variant, #f4f4f7)" }}>
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- a browser preview or a signed storage address, not a static asset
        <img src={src} alt={name} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
      ) : (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", fontSize: 22, color: "var(--on-variant)" }}><i className="ti ti-photo" /></div>
      )}
      <button
        type="button"
        onClick={onRemove}
        disabled={disabled}
        aria-label={`Remove image ${name}`}
        title="Remove"
        style={{ position: "absolute", top: 3, right: 3, width: 20, height: 20, borderRadius: "50%", border: "none", cursor: "pointer", background: "rgba(0,0,0,0.65)", color: "#fff", lineHeight: 1, fontSize: 12 }}
      >
        <i className="ti ti-x" />
      </button>
    </div>
  );
}

interface ToolProps {
  icon:      string;
  label:     string;
  detail:    string;
  count:     number;
  disabled:  boolean;
  onClick:   () => void;
}

/** A small icon button in the toolbar under the Body box, with how many are attached. */
function ToolButton({ icon, label, detail, count, disabled, onClick }: ToolProps) {
  return (
    <button type="button" className="btn btn-ghost btn-sm" onClick={onClick} disabled={disabled} aria-label={label} title={`${label} - ${detail}`} style={{ position: "relative", padding: "4px 8px" }}>
      <i className={`ti ${icon}`} style={{ fontSize: 18 }} />
      {count > 0 && <span style={{ marginLeft: 4, fontSize: 11, fontWeight: 700, color: "var(--primary)" }}>{count}</span>}
    </button>
  );
}

/**
 * Images, PDFs and links for an announcement, kept out of the way: three small icons under the Body box. Clicking one opens the
 * picker (or adds a link row); what has been added then appears below as thumbnails, file chips and link rows. Files can also be
 * dropped on this area.
 */
export default function AttachmentFields({ draft, onChange, showLinkErrors = false, uploadProgress = null, disabled = false }: Props) {
  const imageInput = useRef<HTMLInputElement>(null);
  const documentInput = useRef<HTMLInputElement>(null);
  const [fileErrors, setFileErrors] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const previews = useFilePreviews(draft.newImages);

  const keptImages = draft.existing.filter(item => item.attachment_type === "image" && !draft.removedIds.includes(item.id));
  const keptDocuments = draft.existing.filter(item => item.attachment_type === "document" && !draft.removedIds.includes(item.id));
  const images = imageCount(draft);
  const documents = documentCount(draft);

  function take(kind: AttachmentKind, files: FileList | File[] | null) {
    if (!files || disabled) return;
    const result = addFiles(draft, kind, Array.from(files));
    setFileErrors(result.errors);
    onChange(result.draft);
  }

  /** Dropped files go where their type says: PDFs to the attachments, everything else through the image checks. */
  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const dropped = Array.from(event.dataTransfer.files);
    const pdfs = dropped.filter(file => file.type === "application/pdf");
    const pictures = dropped.filter(file => file.type !== "application/pdf");
    let next = draft;
    let errors: string[] = [];
    for (const [kind, files] of [["image", pictures], ["document", pdfs]] as const) {
      if (!files.length) continue;
      const result = addFiles(next, kind, files);
      next = result.draft;
      errors = errors.concat(result.errors);
    }
    setFileErrors(errors);
    onChange(next);
  }

  return (
    <div
      onDragOver={event => { event.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      style={{
        marginTop: 6, borderRadius: 8, padding: isDragging ? 6 : 0,
        outline: isDragging ? "2px dashed var(--primary)" : "none", background: isDragging ? "rgba(124,58,237,0.06)" : "transparent",
      }}
    >
      {/* ── Toolbar ───────────────────────────────────────────── */}
      <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
        <ToolButton icon="ti-photo-plus" label="Add images" detail={`JPG, PNG or WebP, up to 5 MB each, ${images}/${MAX_IMAGES}`} count={images} disabled={disabled || images >= MAX_IMAGES} onClick={() => imageInput.current?.click()} />
        <ToolButton icon="ti-file-type-pdf" label="Add PDF" detail={`PDF, up to 5 MB each, ${documents}/${MAX_DOCUMENTS}`} count={documents} disabled={disabled || documents >= MAX_DOCUMENTS} onClick={() => documentInput.current?.click()} />
        <ToolButton icon="ti-link" label="Add link" detail={`${draft.links.length}/${MAX_LINKS}`} count={draft.links.length} disabled={disabled || draft.links.length >= MAX_LINKS} onClick={() => onChange(addLink(draft))} />
        <span style={{ ...HINT, marginLeft: 6 }}>Attach pictures, PDFs or links (or drop files here)</span>
        <input ref={imageInput} type="file" multiple hidden accept={IMAGE_ACCEPT} aria-label="Choose images" onChange={event => { take("image", event.target.files); event.target.value = ""; }} />
        <input ref={documentInput} type="file" multiple hidden accept={DOCUMENT_ACCEPT} aria-label="Choose PDF files" onChange={event => { take("document", event.target.files); event.target.value = ""; }} />
      </div>

      {/* ── Pictures ──────────────────────────────────────────── */}
      {(keptImages.length > 0 || draft.newImages.length > 0) && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8 }}>
          {keptImages.map(image => (
            <ImageTile key={image.id} src={image.url || null} name={image.original_filename} disabled={disabled} onRemove={() => onChange(removeExisting(draft, image.id))} />
          ))}
          {draft.newImages.map((file, index) => (
            <ImageTile key={`${file.name}-${index}`} src={previews[index] ?? null} name={file.name} disabled={disabled} onRemove={() => onChange(removeNew(draft, "image", index))} />
          ))}
        </div>
      )}

      {/* ── PDF attachments ───────────────────────────────────── */}
      {(keptDocuments.length > 0 || draft.newDocuments.length > 0) && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 8 }}>
          {keptDocuments.map(document => (
            <div key={document.id} style={ROW}>
              <i className="ti ti-file-type-pdf" style={{ fontSize: 20, color: "var(--error)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{document.original_filename}</div>
                <div style={HINT}>{formatFileSize(document.file_size)}</div>
              </div>
              <a className="btn btn-ghost btn-sm" href={announcementDownloadHref(document.download_path)} target="_blank" rel="noopener noreferrer" aria-label={`Download ${document.original_filename}`}>
                <i className="ti ti-download" />
              </a>
              <button type="button" className="btn btn-ghost btn-sm" disabled={disabled} aria-label={`Remove ${document.original_filename}`} style={{ color: "var(--error)" }} onClick={() => onChange(removeExisting(draft, document.id))}>
                <i className="ti ti-trash" />
              </button>
            </div>
          ))}
          {draft.newDocuments.map((file, index) => (
            <div key={`${file.name}-${index}`} style={ROW}>
              <i className="ti ti-file-type-pdf" style={{ fontSize: 20, color: "var(--error)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</div>
                <div style={HINT}>{formatFileSize(file.size)} · will be uploaded when you publish</div>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" disabled={disabled} aria-label={`Remove ${file.name}`} style={{ color: "var(--error)" }} onClick={() => onChange(removeNew(draft, "document", index))}>
                <i className="ti ti-trash" />
              </button>
            </div>
          ))}
        </div>
      )}

      {fileErrors.length > 0 && (
        <div role="alert" className="field-error-msg" style={{ margin: "8px 0 0" }}>
          {fileErrors.map(message => <div key={message}>{message}</div>)}
        </div>
      )}

      {/* ── External links ────────────────────────────────────── */}
      {draft.links.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
          {draft.links.map((link, index) => {
            const problems = linkProblems(link, showLinkErrors);
            return (
              <div key={link.key} style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
                <div style={{ flex: "1 1 160px", minWidth: 0 }}>
                  <input
                    className={`field-input${problems.title ? " field-error" : ""}`} placeholder="Link title" aria-label={`Link ${index + 1} title`}
                    value={link.title} maxLength={LINK_TITLE_MAX} disabled={disabled}
                    onChange={event => onChange(updateLink(draft, link.key, { title: event.target.value }))}
                  />
                  {problems.title && <div className="field-error-msg">{problems.title}</div>}
                </div>
                <div style={{ flex: "2 1 220px", minWidth: 0 }}>
                  <input
                    className={`field-input${problems.url ? " field-error" : ""}`} placeholder="https://…" aria-label={`Link ${index + 1} address`}
                    value={link.url} inputMode="url" disabled={disabled}
                    onChange={event => onChange(updateLink(draft, link.key, { url: event.target.value }))}
                  />
                  {problems.url && <div className="field-error-msg">{problems.url}</div>}
                </div>
                <button type="button" className="btn btn-ghost btn-sm" disabled={disabled} aria-label={`Remove link ${index + 1}`} style={{ color: "var(--error)" }} onClick={() => onChange(removeLink(draft, link.key))}>
                  <i className="ti ti-trash" />
                </button>
              </div>
            );
          })}
        </div>
      )}

      {uploadProgress !== null && (
        <div aria-live="polite" style={{ marginTop: 8 }}>
          <div style={{ height: 6, borderRadius: 3, background: "var(--outline-v)", overflow: "hidden" }}>
            <div style={{ width: `${uploadProgress}%`, height: "100%", background: "var(--primary)", transition: "width 0.2s" }} />
          </div>
          <div style={{ ...HINT, marginTop: 4 }}>Uploading… {uploadProgress}%</div>
        </div>
      )}
    </div>
  );
}
