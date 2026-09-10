"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { OnboardingFieldConfig } from "@/types/onboardingFieldConfig";

interface Props {
  fields: OnboardingFieldConfig[]; // already filtered to one step, sorted by order
  canEdit: boolean;
  onChanged: () => void;
  onEdit: (field: OnboardingFieldConfig) => void;
}

const TYPE_LABELS: Record<string, string> = {
  text: "Text",
  textarea: "Long text",
  number: "Number",
  date: "Date",
  dropdown: "Dropdown",
  checkbox: "Checkbox",
  file: "File / Image",
};

export default function FieldConfigTable({ fields, canEdit, onChanged, onEdit }: Props) {
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function patch(fieldKey: string, body: Record<string, unknown>) {
    setBusyKey(fieldKey);
    setRowError(null);
    try {
      await clientApi.patch(API.settings.onboardingFields.detail(fieldKey), body);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to update field.");
    } finally {
      setBusyKey(null);
    }
  }

  async function move(field: OnboardingFieldConfig, direction: "up" | "down") {
    const idx = fields.findIndex(f => f.field_key === field.field_key);
    const swapIdx = direction === "up" ? idx - 1 : idx + 1;
    if (swapIdx < 0 || swapIdx >= fields.length) return;
    const other = fields[swapIdx];
    setBusyKey(field.field_key);
    setRowError(null);
    try {
      await Promise.all([
        clientApi.patch(API.settings.onboardingFields.detail(field.field_key), { order: other.order }),
        clientApi.patch(API.settings.onboardingFields.detail(other.field_key), { order: field.order }),
      ]);
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to reorder fields.");
    } finally {
      setBusyKey(null);
    }
  }

  async function remove(field: OnboardingFieldConfig) {
    if (!window.confirm(`Delete the custom field "${field.label}"? Any values employees already entered will be lost.`)) return;
    setBusyKey(field.field_key);
    setRowError(null);
    try {
      await clientApi.delete(API.settings.onboardingFields.detail(field.field_key));
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to delete field.");
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
              <th>Field</th>
              <th style={{ textAlign: "center" }}>Type</th>
              <th style={{ textAlign: "center" }}>Visible</th>
              <th style={{ textAlign: "center" }}>Required</th>
              <th style={{ textAlign: "center" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {fields.map((f, idx) => (
              <tr key={f.field_key}>
                <td>
                  <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(f, "up")}
                      disabled={!canEdit || idx === 0 || busyKey === f.field_key}
                      title="Move up"
                    >
                      <i className="ti ti-chevron-up" style={{ fontSize: 12 }} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 22, height: 18, padding: 0, justifyContent: "center" }}
                      onClick={() => move(f, "down")}
                      disabled={!canEdit || idx === fields.length - 1 || busyKey === f.field_key}
                      title="Move down"
                    >
                      <i className="ti ti-chevron-down" style={{ fontSize: 12 }} />
                    </button>
                  </div>
                </td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontWeight: 600, fontSize: 13 }}>{f.label}</span>
                    {f.is_custom && <span className="badge badge-info">Custom</span>}
                    {f.is_locked && (
                      <span title="Always required — can't be hidden or made optional">
                        <i className="ti ti-lock" style={{ fontSize: 13, color: "var(--on-variant)" }} />
                      </span>
                    )}
                  </div>
                </td>
                <td style={{ textAlign: "center", fontSize: 12, color: "var(--on-variant)" }}>
                  {TYPE_LABELS[f.field_type] ?? f.field_type}
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={f.visible}
                    disabled={!canEdit || f.is_locked || busyKey === f.field_key}
                    onChange={e => patch(f.field_key, { visible: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={f.required}
                    disabled={!canEdit || f.is_locked || busyKey === f.field_key}
                    onChange={e => patch(f.field_key, { required: e.target.checked })}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <div style={{ display: "inline-flex", gap: 6 }}>
                    <button
                      className="btn btn-ghost"
                      style={{
                        width: 28, height: 28, padding: 0, justifyContent: "center",
                        border: "1px solid var(--outline-v)", borderRadius: 6,
                      }}
                      onClick={() => onEdit(f)}
                      disabled={!canEdit || busyKey === f.field_key}
                      title="Edit label / options"
                    >
                      <i className="ti ti-pencil" style={{ fontSize: 13 }} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{
                        width: 28, height: 28, padding: 0, justifyContent: "center",
                        border: "1px solid var(--outline-v)", borderRadius: 6,
                        color: f.is_custom ? "var(--error)" : "var(--outline)",
                        cursor: f.is_custom ? "pointer" : "not-allowed",
                      }}
                      onClick={() => remove(f)}
                      disabled={!canEdit || !f.is_custom || busyKey === f.field_key}
                      title={f.is_custom ? "Delete custom field" : "Built-in fields can't be deleted — hide them instead"}
                    >
                      <i className="ti ti-trash" style={{ fontSize: 13 }} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {fields.length === 0 && (
              <tr>
                <td colSpan={6} style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)" }}>
                  No fields configured for this step.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
