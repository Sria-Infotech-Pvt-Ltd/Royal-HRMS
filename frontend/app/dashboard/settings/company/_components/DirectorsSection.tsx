"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { Director } from "@/types/company";
import ProfileCard from "./ProfileCard";
import type { PeopleConfig } from "../_data";

interface Row {
  key: string;
  id: string | null;
  din: string;
  name: string;
  designation: string;
  saving: boolean;
  error: string | null;
}

function toRow(d: Director): Row {
  return { key: d.id, id: d.id, din: d.din, name: d.name, designation: d.designation, saving: false, error: null };
}

let tempCounter = 0;

const DESIGNATION_PLACEHOLDERS: Record<string, string> = {
  director: "Managing Director",
  "designated partner": "Designated Partner",
  partner: "Managing Partner",
  trustee: "Chairperson",
  "member/manager": "Manager",
};

interface Props {
  canEdit: boolean;
  config: PeopleConfig;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

// How the ID input filters/limits keystrokes for each entity type's ID
// format — "din" (company DIN or LLP DPIN) is 8-digit numeric, "pan"
// (Partnership partner / Trust trustee) is a 10-character uppercase
// alphanumeric PAN, "free" (foreign entity types) takes whatever is typed.
function sanitizeId(raw: string, format: PeopleConfig["idFormat"]): string {
  if (format === "din") return raw.replace(/\D/g, "").slice(0, 8);
  if (format === "pan") return raw.toUpperCase().slice(0, 10);
  return raw;
}

export default function DirectorsSection({ canEdit, config, collapsed, onToggleCollapse }: Props) {
  const { sectionTitle, idLabel, idFormat, singular } = config;
  const idPlaceholder = idFormat === "din" ? "01234567" : idFormat === "pan" ? "AAAAA0000A" : "";
  const idMaxLength = idFormat === "din" ? 8 : idFormat === "pan" ? 10 : undefined;
  const designationPlaceholder = DESIGNATION_PLACEHOLDERS[singular] ?? "Managing Director";
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await clientApi.get(`${API.settings.directors.list}?page_size=100`);
      const results: Director[] = res.data?.data?.results ?? [];
      setRows(results.map(toRow));
    } catch (err: unknown) {
      setLoadError((err as { message?: string })?.message ?? "Failed to load directors.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function updateRow(key: string, patch: Partial<Row>) {
    setRows(prev => prev.map(r => (r.key === key ? { ...r, ...patch, error: null } : r)));
  }

  function addRow() {
    const key = `new-${++tempCounter}`;
    setRows(prev => [...prev, { key, id: null, din: "", name: "", designation: "", saving: false, error: null }]);
  }

  async function removeRow(row: Row) {
    if (row.id) {
      if (!window.confirm(`Remove director "${row.name}"?`)) return;
      try {
        await clientApi.delete(API.settings.directors.detail(row.id));
      } catch (err: unknown) {
        updateRow(row.key, { error: (err as { message?: string })?.message ?? "Failed to remove." });
        return;
      }
    }
    setRows(prev => prev.filter(r => r.key !== row.key));
  }

  async function saveRow(row: Row) {
    if (!row.din.trim() || !row.name.trim() || !row.designation.trim()) return;
    updateRow(row.key, { saving: true });
    const payload = { din: row.din.trim(), name: row.name.trim(), designation: row.designation.trim() };
    try {
      if (row.id) {
        await clientApi.put(API.settings.directors.detail(row.id), payload);
        updateRow(row.key, { saving: false });
      } else {
        const res = await clientApi.post(API.settings.directors.list, payload);
        const saved: Director = res.data.data;
        setRows(prev => prev.map(r => (r.key === row.key ? { ...toRow(saved), key: saved.id } : r)));
      }
    } catch (err: unknown) {
      const e = err as { message?: string; data?: Record<string, string[]> };
      const msg = e.data ? Object.values(e.data)[0]?.[0] ?? e.message : e.message;
      updateRow(row.key, { saving: false, error: msg ?? "Failed to save." });
    }
  }

  return (
    <ProfileCard
      icon="ti-users-group"
      title={sectionTitle}
      subtitle={`Each ${singular}'s ${idLabel}, name, and designation.`}
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
    >
      {loading && <div style={{ color: "var(--on-variant)", fontSize: 13, padding: "8px 0" }}>Loading…</div>}
      {loadError && <div style={{ color: "var(--error)", fontSize: 13, padding: "8px 0" }}>{loadError}</div>}
      {!loading && !loadError && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{idLabel} <span style={{ color: "var(--error)" }}>*</span></th>
                <th>Name <span style={{ color: "var(--error)" }}>*</span></th>
                <th>Designation <span style={{ color: "var(--error)" }}>*</span></th>
                <th style={{ width: 36 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.key}>
                  <td style={{ minWidth: 120 }}>
                    <input
                      className="field-input"
                      style={{ fontFamily: "monospace" }}
                      value={row.din}
                      disabled={!canEdit}
                      maxLength={idMaxLength}
                      onChange={e => updateRow(row.key, { din: sanitizeId(e.target.value, idFormat) })}
                      onBlur={() => saveRow(row)}
                      placeholder={idPlaceholder}
                    />
                    {row.error && <div className="field-error-msg">{row.error}</div>}
                  </td>
                  <td style={{ minWidth: 180 }}>
                    <input
                      className="field-input"
                      value={row.name}
                      disabled={!canEdit}
                      onChange={e => updateRow(row.key, { name: e.target.value })}
                      onBlur={() => saveRow(row)}
                    />
                  </td>
                  <td style={{ minWidth: 160 }}>
                    <input
                      className="field-input"
                      value={row.designation}
                      disabled={!canEdit}
                      onChange={e => updateRow(row.key, { designation: e.target.value })}
                      onBlur={() => saveRow(row)}
                      placeholder={designationPlaceholder}
                    />
                  </td>
                  <td style={{ textAlign: "center" }}>
                    {canEdit && (
                      <button
                        type="button"
                        className="btn btn-ghost"
                        style={{ width: 28, height: 28, padding: 0, justifyContent: "center", color: "var(--error)" }}
                        onClick={() => removeRow(row)}
                        disabled={row.saving}
                        title="Remove"
                        aria-label={`Remove ${row.name || singular}`}
                      >
                        <i className="ti ti-trash" style={{ fontSize: 13 }} />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {rows.length === 0 && (
            <div style={{ textAlign: "center", padding: "20px 0", color: "var(--on-variant)", fontSize: 13 }}>
              No {sectionTitle.toLowerCase()} added yet.
            </div>
          )}
        </div>
      )}
      {canEdit && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 12, color: "var(--primary)" }} onClick={addRow}>
          <i className="ti ti-plus" /> Add {singular}
        </button>
      )}
    </ProfileCard>
  );
}
