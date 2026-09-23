"use client";

import { useState } from "react";
import { type DocEntry } from "../../_data";
import DocPreviewModal from "@/components/DocPreviewModal";

/* ── Joining Document — table with Verified / Pending status ── */
export default function DocsTable({ documents }: { documents: DocEntry[] }) {
  const [preview, setPreview] = useState<DocEntry | null>(null);
  return (
    <>
      {preview && preview.fileUrl && (
        <DocPreviewModal
          name={preview.name}
          fileName={preview.fileName}
          fileUrl={preview.fileUrl}
          fileSize={preview.fileSize}
          onClose={() => setPreview(null)}
        />
      )}
    <div>
      {/* Info banner */}
      <div
        className="flex items-center gap-2.5 px-4 py-3 rounded-lg mb-5"
        style={{ background: "rgba(124,58,237,0.06)", border: "1px solid rgba(124,58,237,0.15)" }}
      >
        <i className="ti ti-info-circle text-[16px]" style={{ color: "var(--primary)" }} />
        <p className="text-[13px]" style={{ color: "var(--primary)" }}>
          Joining documents are mandatory and locked once verified by HR.
        </p>
      </div>

      {/* Status table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--outline-v)" }}>
        <table className="w-full border-collapse">
          <thead>
            <tr style={{ background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)" }}>
              {["Document", "Required", "Status", "Uploaded On", "Action"].map((h) => (
                <th
                  key={h}
                  className="text-left text-[11px] font-semibold uppercase tracking-wide px-4 py-3 whitespace-nowrap"
                  style={{ color: "var(--on-variant)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr
                key={doc.name}
                className="border-b last:border-0"
                style={{ borderColor: "var(--outline-v)" }}
              >
                {/* Document name */}
                <td className="px-4 py-3.5">
                  <span className="text-[13px] font-semibold" style={{ color: "var(--on-bg)" }}>
                    {doc.name}
                  </span>
                </td>

                {/* Required */}
                <td className="px-4 py-3.5">
                  <span className="text-[13px]" style={{ color: "var(--on-variant)" }}>
                    {doc.required ? "Yes" : "No"}
                  </span>
                </td>

                {/* Status badge */}
                <td className="px-4 py-3.5">
                  {doc.status === "verified" && (
                    <span
                      className="inline-flex items-center px-3 py-0.5 rounded-full text-[12px] font-medium"
                      style={{ background: "rgba(23,144,90,0.12)", color: "#17905a" }}
                    >
                      Verified
                    </span>
                  )}
                  {doc.status === "pending" && (
                    <span
                      className="inline-flex items-center px-3 py-0.5 rounded-full text-[12px] font-medium"
                      style={{ background: "rgba(234,179,8,0.15)", color: "#b45309" }}
                    >
                      Pending
                    </span>
                  )}
                  {!doc.status && (
                    <span className="text-[13px]" style={{ color: "var(--on-variant)" }}>—</span>
                  )}
                </td>

                {/* Uploaded on */}
                <td className="px-4 py-3.5">
                  <span
                    className="text-[13px]"
                    style={{ color: doc.uploadedOn ? "var(--primary)" : "var(--on-variant)" }}
                  >
                    {doc.uploadedOn ?? "—"}
                  </span>
                </td>

                {/* Action */}
                <td className="px-4 py-3.5">
                  <button
                    suppressHydrationWarning
                    disabled={!doc.fileUrl}
                    onClick={() => doc.fileUrl && setPreview(doc)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12.5px] font-medium transition-colors hover:bg-[var(--bg-mid)] disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--outline-v)", color: "var(--on-bg)", background: "var(--surface)" }}
                  >
                    <i className="ti ti-eye text-[13px]" />
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}
