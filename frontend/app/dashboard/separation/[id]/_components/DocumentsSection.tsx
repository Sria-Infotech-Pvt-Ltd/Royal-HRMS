"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { SeparationDocumentItem, SeparationRequest } from "@/types/separation";
import type { SeparationAccess } from "../../_access";
import { fmtDateTime } from "../../_workflow";

interface Props {
  r:      SeparationRequest;
  access: SeparationAccess;
}

const ALLOWED_DOC_TYPES = ["application/pdf", "image/jpeg", "image/png"];
const MAX_DOC_BYTES = 5 * 1024 * 1024;

export default function DocumentsSection({ r, access }: Props) {
  const { showToast } = useToast();
  const { data: documents, loading, refetch } = useFetch<SeparationDocumentItem[]>(API.separation.documents(r.id));
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const rows = documents ?? [];
  const canManage = access.canPickEmployee || access.canApprove;

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (file.size > MAX_DOC_BYTES) { showToast(`"${file.name}" exceeds 5 MB.`, "error"); return; }
    if (!ALLOWED_DOC_TYPES.includes(file.type)) { showToast(`"${file.name}" must be PDF, JPG, or PNG.`, "error"); return; }

    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("document", file);
      await clientApi.post(API.separation.documents(r.id), fd, { headers: { "Content-Type": "multipart/form-data" } });
      showToast("Document uploaded.", "success");
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to upload document."), "error");
    } finally {
      setUploading(false);
    }
  }

  async function deleteDocument(doc: SeparationDocumentItem) {
    try {
      await clientApi.delete(API.separation.documentDetail(r.id, doc.id));
      showToast("Document deleted.", "success");
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to delete document."), "error");
    }
  }

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-files" /> Documents</span>
        {canManage && (
          <button className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()} disabled={uploading} suppressHydrationWarning>
            {uploading ? <><i className="ti ti-loader-2 spin" /> Uploading…</> : <><i className="ti ti-upload" /> Attach Document</>}
          </button>
        )}
        <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png" onChange={handleFile} />
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> Loading…</p>
        ) : rows.length === 0 ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>No documents attached yet.</p>
        ) : (
          rows.map(d => {
            const url = d.document_url || d.url;
            const name = d.name || d.file_name || "Document";
            return (
              <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", border: "1px solid var(--outline-v)", borderRadius: 8, padding: "8px 12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
                  <i className="ti ti-file" style={{ color: "var(--primary)" }} />
                  <div style={{ minWidth: 0 }}>
                    {url ? (
                      <a href={url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, fontWeight: 500, color: "var(--primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                        {name}
                      </a>
                    ) : (
                      <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{name}</div>
                    )}
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                      {d.uploaded_by_name ? `${d.uploaded_by_name} · ` : ""}{fmtDateTime(d.uploaded_at || d.created_at)}
                    </div>
                  </div>
                </div>
                {canManage && (
                  <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => deleteDocument(d)} suppressHydrationWarning>
                    <i className="ti ti-trash" />
                  </button>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
