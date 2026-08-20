"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";

interface Props {
  types: DocumentTypeConfig[]; // already sorted by order
  canEdit: boolean;
  onChanged: () => void;
}

export default function DocumentTypeConfigTable({ types, canEdit, onChanged }: Props) {
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function patch(typeKey: string, body: Record<string, unknown>) {
    setBusyKey(typeKey);
    setRowError(null);
    try {
      await clientApi.patch(API.settings.documentTypes.detail(typeKey), body);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to update document type.");
    } finally {
      setBusyKey(null);
    }
  }

  async function move(type: DocumentTypeConfig, direction: "up" | "down") {
    const idx = types.findIndex(t => t.type_key === type.type_key);
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
      setRowError((err as { message?: string })?.message ?? "Failed to reorder document types.");
    } finally {
      setBusyKey(null);
    }
  }

  async function remove(type: DocumentTypeConfig) {
    if (!window.confirm(`Delete the custom document type "${type.label}"? Any files employees already uploaded will be lost.`)) return;
    setBusyKey(type.type_key);
    setRowError(null);
    try {
      await clientApi.delete(API.settings.documentTypes.detail(type.type_key));
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to delete document type.");
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
              <th style={{ width: 60 }}>Order</th>
              <th>Document</th>
              <th style={{ textAlign: "center" }}>Multiple</th>
              <th style={{ textAlign: "center" }}>Visible</th>
              <th style={{ textAlign: "center" }}>Required</th>
              <th style={{ textAlign: "center" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {types.map((t, idx) => (
              <tr key={t.type_key}>
                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(t, "up")}
                      disabled={!canEdit || idx === 0 || busyKey === t.type_key}
                      title="Move up"
                    >
                      <i className="ti ti-chevron-up" style={{ fontSize: 12 }} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(t, "down")}
                      disabled={!canEdit || idx === types.length - 1 || busyKey === t.type_key}
                      title="Move down"
                    >
                      <i className="ti ti-chevron-down" style={{ fontSize: 12 }} />
                    </button>
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{t.label}</span>
                    {t.is_custom && <span className="badge badge-info">Custom</span>}
                  </div>
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={t.allow_multiple}
                    disabled={!canEdit || busyKey === t.type_key}
                    onChange={e => patch(t.type_key, { allow_multiple: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={t.visible}
                    disabled={!canEdit || busyKey === t.type_key}
                    onChange={e => patch(t.type_key, { visible: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={t.required}
                    disabled={!canEdit || busyKey === t.type_key}
                    onChange={e => patch(t.type_key, { required: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <button
                    className="btn btn-ghost"
                    style={{
                      width: 28, height: 28, padding: 0, justifyContent: "center",
                      border: "1px solid var(--outline-v)", borderRadius: 6,
                      color: t.is_custom ? "var(--error)" : "var(--outline)",
                      cursor: t.is_custom ? "pointer" : "not-allowed",
                    }}
                    onClick={() => remove(t)}
                    disabled={!canEdit || !t.is_custom || busyKey === t.type_key}
                    title={t.is_custom ? "Delete custom document type" : "Built-in document types can't be deleted — hide them instead"}
                  >
                    <i className="ti ti-trash" style={{ fontSize: 13 }} />
                  </button>
                </td>
              </tr>
            ))}
            {types.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)" }}>
                  No document types configured.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
