"use client";

// HR preview of a course material (no progress is recorded — that only
// happens in My Learning for assigned employees).

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { embedUrl, fileUrl, type Material } from "@/lib/training";
import { PdfFrame } from "@/app/dashboard/my-learning/_components/MaterialViewer";

const FRAME: React.CSSProperties = { position: "absolute", inset: 0, width: "100%", height: "100%", border: 0, borderRadius: 8 };

function UploadedVideo({ material }: { material: Material }) {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    clientApi.get<{ data: { url: string | null } }>(API.training.videoSource(material.id))
      .then(r => { if (alive) setSrc(r.data.data.url || fileUrl(material.id)); })
      .catch(() => { if (alive) setSrc(fileUrl(material.id)); });
    return () => { alive = false; };
  }, [material.id]);
  if (!src) return <div className="text-[13px] text-[var(--on-variant)] py-4">Loading video…</div>;
  return (
    <video src={src} controls preload="metadata" playsInline
           style={{ width: "100%", maxHeight: "60vh", borderRadius: 8, background: "#000" }} />
  );
}

export default function MaterialPreview({ material: m }: { material: Material }) {
  if (m.material_type === "video") return <UploadedVideo material={m} />;

  if (m.material_type === "document") {
    if (m.file_format === "pdf") return <PdfFrame materialId={m.id} title={m.title} />;
    return (
      <div className="text-[13px]" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span className="text-[var(--on-variant)]">
          {m.file_format.toUpperCase()} files can&apos;t be shown in the browser — they open in PowerPoint / Word.
        </span>
        <a href={fileUrl(m.id)} download className="btn btn-outline btn-sm"><i className="ti ti-download" /> Download</a>
      </div>
    );
  }

  // External link
  return (
    <div>
      {m.provider === "direct" ? (
        <video src={m.external_url} controls preload="metadata" playsInline
               style={{ width: "100%", maxHeight: "60vh", borderRadius: 8, background: "#000" }} />
      ) : (
        <div style={{ position: "relative", paddingTop: "56.25%" }}>
          <iframe src={embedUrl(m)} title={m.title} style={FRAME}
                  allow="accelerometer; encrypted-media; picture-in-picture; fullscreen" allowFullScreen
                  referrerPolicy="strict-origin-when-cross-origin" sandbox="allow-scripts allow-same-origin allow-presentation" />
        </div>
      )}
      <a href={m.external_url} target="_blank" rel="noopener noreferrer"
         className="text-[12px] text-[var(--primary)]" style={{ display: "inline-block", marginTop: 8 }}>
        Open the original <i className="ti ti-external-link" />
      </a>
    </div>
  );
}
