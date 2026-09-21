"use client";

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface DocPreviewModalProps {
  name: string;
  fileName?: string;
  fileUrl: string;
  fileSize?: number;
  onClose: () => void;
}

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function isImage(fileName: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg|bmp)$/i.test(fileName);
}

// Django API URLs (http://host:port/api/...) must be fetched through the
// Next.js proxy so auth cookies are sent from the same origin.
function resolveUrl(url: string): string {
  try {
    const { pathname } = new URL(url);
    if (pathname.startsWith("/api/")) return pathname;
  } catch { /* relative URL or Cloudinary — pass through */ }
  return url;
}

export default function DocPreviewModal({
  name, fileName, fileUrl, fileSize, onClose,
}: DocPreviewModalProps) {
  const close = useCallback(() => onClose(), [onClose]);

  const resolvedUrl = resolveUrl(fileUrl);
  const fileIsImage = isImage(fileName ?? "");

  // For PDFs: fetch the file client-side, stamp the correct MIME type,
  // and hand Chrome a local blob: URL. This sidesteps Cloudinary's
  // raw/upload serving without Content-Type: application/pdf.
  const [blobUrl,  setBlobUrl]  = useState<string | null>(null);
  const [loading,  setLoading]  = useState(!fileIsImage);
  const [fetchErr, setFetchErr] = useState(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [close]);

  useEffect(() => {
    if (fileIsImage || !resolvedUrl) return;

    let created: string | null = null;
    setLoading(true);
    setFetchErr(false);

    // Only send auth cookies for local proxy paths — external URLs (Cloudinary etc.)
    // reject credentialed cross-origin requests with 401.
    const fetchOpts: RequestInit = resolvedUrl.startsWith("/api/")
      ? { credentials: "include" }
      : {};

    fetch(resolvedUrl, fetchOpts)
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.arrayBuffer();
      })
      .then(buf => {
        const blob = new Blob([buf], { type: "application/pdf" });
        created = URL.createObjectURL(blob);
        setBlobUrl(created);
      })
      .catch(() => setFetchErr(true))
      .finally(() => setLoading(false));

    return () => {
      if (created) URL.revokeObjectURL(created);
    };
  }, [resolvedUrl, fileIsImage]);

  const overlay = (
    <div
      className="fixed inset-0 flex items-center justify-center p-6"
      style={{ background: "rgba(0,0,0,0.55)", zIndex: 9999 }}
      onClick={onClose}
    >
      <div
        className="relative flex flex-col rounded-2xl overflow-hidden shadow-2xl"
        style={{ background: "var(--surface)", width: "min(860px, 92vw)", maxHeight: "88vh" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3.5 flex-shrink-0"
          style={{ background: "var(--primary)" }}
        >
          <div className="flex items-center gap-2.5">
            <i className="ti ti-file-description text-white text-[18px]" />
            <div>
              <p className="text-[14px] font-semibold text-white leading-tight">{name}</p>
              {fileName && (
                <p className="text-[11.5px] text-white/70 leading-tight">
                  {fileName}{fileSize ? ` · ${fmtBytes(fileSize)}` : ""}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {!fileIsImage && (
              <a
                href={resolvedUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-white/90 hover:bg-white/15 transition-colors text-[12px] font-medium"
              >
                <i className="ti ti-external-link text-[15px]" />
                Open
              </a>
            )}
            <button
              onClick={onClose}
              suppressHydrationWarning
              className="w-8 h-8 flex items-center justify-center rounded-lg text-white/80 hover:bg-white/15 transition-colors"
            >
              <i className="ti ti-x text-[18px]" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div
          className="flex-1 overflow-auto bg-[#f4f6fb] flex items-center justify-center p-4"
          style={{ minHeight: 0 }}
        >
          {fileIsImage ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img
              src={resolvedUrl}
              alt={name}
              className="max-w-full max-h-full rounded-lg shadow object-contain"
              style={{ maxHeight: "calc(88vh - 120px)" }}
            />
          ) : loading ? (
            <div className="flex flex-col items-center gap-3 text-gray-400">
              <i className="ti ti-loader-2 animate-spin text-[36px]" />
              <span className="text-[13px]">Loading PDF…</span>
            </div>
          ) : fetchErr ? (
            <div className="flex flex-col items-center gap-4 py-12 px-6 text-center">
              <i className="ti ti-file-off text-[48px] text-gray-300" />
              <p className="text-[14px] text-gray-500">Could not load the PDF inline.</p>
              <a
                href={resolvedUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-[13px] font-semibold"
                style={{ background: "var(--primary)" }}
              >
                <i className="ti ti-external-link text-[15px]" />
                Open in new tab
              </a>
            </div>
          ) : (
            <iframe
              src={blobUrl ?? ""}
              title={name}
              className="w-full rounded-lg border-0"
              style={{ height: "calc(88vh - 120px)" }}
            />
          )}
        </div>
      </div>
    </div>
  );

  return createPortal(overlay, document.body ?? document.documentElement);
}
