import {
  announcementDownloadHref, formatFileSize, isSafeHttpUrl,
  type AnnouncementAttachment, type AnnouncementLink,
} from "@/lib/announcementAttachments";

interface MediaProps {
  attachments?: AnnouncementAttachment[];
  links?:       AnnouncementLink[];
}

const SECTION_LABEL = { fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.05em", margin: "16px 0 8px" } as const;

/** Everything attached to an announcement, for its detail view: pictures, PDFs (with a download button) and links. */
export default function AnnouncementMedia({ attachments = [], links = [] }: MediaProps) {
  const images = attachments.filter(item => item.attachment_type === "image");
  const documents = attachments.filter(item => item.attachment_type === "document");
  const shownLinks = links.filter(link => link.title.trim() !== "");
  if (!images.length && !documents.length && !shownLinks.length) return null;

  return (
    <div className="ann-media" style={{ marginTop: 12 }}>
      {images.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: images.length === 1 ? "1fr" : "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
          {images.map(image => (
            <a key={image.id} href={image.url} target="_blank" rel="noopener noreferrer" title={image.original_filename}>
              {/* eslint-disable-next-line @next/next/no-img-element -- a short-lived signed storage address, not a static asset */}
              <img
                src={image.url}
                alt={image.original_filename}
                loading="lazy"
                style={{ width: "100%", maxHeight: images.length === 1 ? 420 : 200, objectFit: "cover", borderRadius: 8, border: "1px solid var(--outline-v)", display: "block" }}
              />
            </a>
          ))}
        </div>
      )}

      {documents.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Attachments</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {documents.map(document => (
              <div key={document.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 12px", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
                <i className="ti ti-file-type-pdf" style={{ fontSize: 22, color: "var(--error)", flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{document.original_filename}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{formatFileSize(document.file_size)}</div>
                </div>
                <a
                  className="btn btn-ghost btn-sm"
                  href={announcementDownloadHref(document.download_path)}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={`Download ${document.original_filename}`}
                >
                  <i className="ti ti-download" /> Download
                </a>
              </div>
            ))}
          </div>
        </>
      )}

      {shownLinks.length > 0 && (
        <>
          <div style={SECTION_LABEL}>Links</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {shownLinks.map((link, index) => (
              isSafeHttpUrl(link.url) ? (
                <a key={`${link.url}-${index}`} className="btn btn-ghost btn-sm" href={link.url} target="_blank" rel="noopener noreferrer">
                  <i className="ti ti-external-link" /> {link.title}
                </a>
              ) : (
                <span key={`${link.url}-${index}`} className="btn btn-ghost btn-sm" style={{ opacity: 0.6, cursor: "default" }}>{link.title}</span>
              )
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/** The small version for a list card: the first picture and a count of what else is attached. */
export function AnnouncementMediaPreview({ attachments = [], links = [] }: MediaProps) {
  const images = attachments.filter(item => item.attachment_type === "image");
  const documents = attachments.filter(item => item.attachment_type === "document");
  if (!images.length && !documents.length && !links.length) return null;
  const chips = [
    images.length > 1 ? `${images.length} images` : "",
    documents.length ? `${documents.length} PDF${documents.length > 1 ? "s" : ""}` : "",
    links.length ? `${links.length} link${links.length > 1 ? "s" : ""}` : "",
  ].filter(Boolean);

  return (
    <div style={{ marginTop: 10 }}>
      {images.length > 0 && (
        // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed storage address, not a static asset
        <img src={images[0].url} alt={images[0].original_filename} loading="lazy"
          style={{ width: "100%", maxHeight: 180, objectFit: "cover", borderRadius: 8, border: "1px solid var(--outline-v)", display: "block" }} />
      )}
      {chips.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: images.length ? 8 : 0 }}>
          {chips.map(chip => (
            <span key={chip} className="badge badge-neutral" style={{ fontSize: 10 }}><i className="ti ti-paperclip" /> {chip}</span>
          ))}
        </div>
      )}
    </div>
  );
}
