"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { confirmDialog } from "@/components/DialogProvider";

interface Props {
  types: DocumentTypeConfig[]; // already sorted by order
  canEdit: boolean;
  onChanged: () => void;
}

export default function DocumentTypeConfigTable({ types, canEdit, onChanged }: Props) {
  const t = useT();
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function patch(typeKey: string, body: Record<string, unknown>) {
    setBusyKey(typeKey);
    setRowError(null);
    try {
      await clientApi.patch(API.settings.documentTypes.detail(typeKey), body);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? t("Failed to update document type."));
    } finally {
      setBusyKey(null);
    }
  }

  async function move(type: DocumentTypeConfig, direction: "up" | "down") {
    const idx = types.findIndex(docType => docType.type_key === type.type_key);
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= types.length) return;
    const other = types[swapIdx];
    setBusyKey(type.type_key);
    setRowError(null);
    try {
      await Promise.all([
        clientApi.patch(API.settings.documentTypes.detail(type.type_key), { order: other.order }),
        clientApi.patch(API.settings.documentTypes.detail(other.type_key), { order: type.order }),
      ]);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? t("Failed to reorder document types."));
    } finally {
      setBusyKey(null);
    }
  }

  async function remove(type: DocumentTypeConfig) {
    if (!(await confirmDialog(t("Delete the custom document type \"{label}\"? Any files employees already uploaded will be lost.", { label: type.label })))) return;
    setBusyKey(type.type_key);
    setRowError(null);
    try {
      await clientApi.delete(API.settings.documentTypes.detail(type.type_key));
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? t("Failed to delete document type."));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <>
      {rowError && (
        <div style={{ margin: "0 24px 16px", padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {rowError}
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 60 }}>{t("Order")}</th>
              <th>{t("Document")}</th>
              <th style={{ textAlign: "center" }}>{t("Multiple")}</th>
              <th style={{ textAlign: "center" }}>{t("Visible")}</th>
              <th style={{ textAlign: "center" }}>{t("Required")}</th>
              <th style={{ textAlign: "center" }}>{t("Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {types.map((docType, idx) => (
              <tr key={docType.type_key}>
                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(docType, "up")}
                      disabled={!canEdit || idx === 0 || busyKey === docType.type_key}
                      title={t("Move up")}
                     aria-label={t("Move up")}>
                      <i className="ti ti-chevron-up" style={{ fontSize: 12 }} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(docType, "down")}
                      disabled={!canEdit || idx === types.length - 1 || busyKey === docType.type_key}
                      title={t("Move down")}
                     aria-label={t("Move down")}>
                      <i className="ti ti-chevron-down" style={{ fontSize: 12 }} />
                    </button>
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{docType.label}</span>
                    {docType.is_custom && <span className="badge badge-info">{t("Custom")}</span>}
                  </div>
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={docType.allow_multiple}
                    disabled={!canEdit || busyKey === docType.type_key}
                    onChange={e => patch(docType.type_key, { allow_multiple: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={docType.visible}
                    disabled={!canEdit || busyKey === docType.type_key}
                    onChange={e => patch(docType.type_key, { visible: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={docType.required}
                    disabled={!canEdit || busyKey === docType.type_key}
                    onChange={e => patch(docType.type_key, { required: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <button
                    className="btn btn-ghost"
                    style={{
                      width: 28, height: 28, padding: 0, justifyContent: "center",
                      border: "1px solid var(--outline-v)", borderRadius: 6,
                      color: docType.is_custom ? "var(--error)" : "var(--outline)",
                      cursor: docType.is_custom ? "pointer" : "not-allowed",
                    }}
                    onClick={() => remove(docType)}
                    disabled={!canEdit || !docType.is_custom || busyKey === docType.type_key}
                    title={docType.is_custom ? t("Delete custom document type") : t("Built-in document types can't be deleted — hide them instead")}
                   aria-label={t("Delete")}>
                    <i className="ti ti-trash" style={{ fontSize: 13 }} />
                  </button>
                </td>
              </tr>
            ))}
            {types.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)" }}>
                  {t("No document types configured.")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
