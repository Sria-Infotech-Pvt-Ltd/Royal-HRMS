"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { GSTRegistration } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { GST_REGISTRATION_TYPE_OPTIONS, STATES, gstinLiveStatus } from "../_data";

interface Row {
  key: string; // real id once saved, a local temp key before that
  id: string | null;
  gstin: string;
  state: string;
  registration_type: string;
  place_of_business: string;
  saving: boolean;
  error: string | null;
}

function toRow(r: GSTRegistration): Row {
  return {
    key: r.id, id: r.id, gstin: r.gstin, state: r.state,
    registration_type: r.registration_type, place_of_business: r.place_of_business,
    saving: false, error: null,
  };
}

let tempCounter = 0;

export default function GSTRegistrationsSection({ canEdit, companyPan }: { canEdit: boolean; companyPan: string }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const res = await clientApi.get(`${API.settings.gstRegistrations.list}?page_size=100`);
      const results: GSTRegistration[] = res.data?.data?.results ?? [];
      setRows(results.map(toRow));
    } catch (err: unknown) {
      setLoadError((err as { message?: string })?.message ?? "Failed to load GST registrations.");
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
    setRows(prev => [...prev, {
      key, id: null, gstin: "", state: "", registration_type: "regular",
      place_of_business: "", saving: false, error: null,
    }]);
  }

  async function removeRow(row: Row) {
    if (row.id) {
      if (!window.confirm(`Remove the GST registration for ${row.state} (${row.gstin})?`)) return;
      try {
        await clientApi.delete(API.settings.gstRegistrations.detail(row.id));
      } catch (err: unknown) {
        updateRow(row.key, { error: (err as { message?: string })?.message ?? "Failed to remove." });
        return;
      }
    }
    setRows(prev => prev.filter(r => r.key !== row.key));
  }

  async function saveRow(row: Row) {
    if (!row.gstin.trim() || !row.state) return; // wait for both before persisting
    updateRow(row.key, { saving: true });
    const payload = {
      gstin: row.gstin.trim().toUpperCase(), state: row.state,
      registration_type: row.registration_type, place_of_business: row.place_of_business.trim(),
    };
    try {
      if (row.id) {
        await clientApi.put(API.settings.gstRegistrations.detail(row.id), payload);
        updateRow(row.key, { saving: false });
      } else {
        const res = await clientApi.post(API.settings.gstRegistrations.list, payload);
        const saved: GSTRegistration = res.data.data;
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
      icon="ti-file-invoice"
      title="GST registrations"
      subtitle="State-wise. One GSTIN per state. Each is checked against your PAN."
    >
      {loading && <div style={{ color: "var(--on-variant)", fontSize: 13, padding: "8px 0" }}>Loading…</div>}
      {loadError && <div style={{ color: "var(--error)", fontSize: 13, padding: "8px 0" }}>{loadError}</div>}
      {!loading && !loadError && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>GSTIN</th>
                <th>State</th>
                <th>Type</th>
                <th>Place of business</th>
                <th style={{ width: 36 }} />
              </tr>
            </thead>
            <tbody>
              {rows.map(row => {
                const status = gstinLiveStatus(row.gstin, companyPan, row.state);
                return (
                  <tr key={row.key}>
                    <td style={{ minWidth: 180 }}>
                      <input
                        className="field-input"
                        style={{ fontFamily: "monospace" }}
                        value={row.gstin}
                        disabled={!canEdit}
                        maxLength={15}
                        onChange={e => updateRow(row.key, { gstin: e.target.value.toUpperCase() })}
                        onBlur={() => saveRow(row)}
                        placeholder="22AAAAA0000A1Z5"
                      />
                      {status && (
                        <div style={{ fontSize: 11, marginTop: 4, color: status.ok ? "var(--success)" : "var(--error)" }}>
                          <i className={`ti ${status.ok ? "ti-check" : "ti-x"}`} style={{ marginRight: 3 }} />
                          {status.text}
                        </div>
                      )}
                      {row.error && <div className="field-error-msg">{row.error}</div>}
                    </td>
                    <td style={{ minWidth: 150 }}>
                      <select
                        className="field-input"
                        value={row.state}
                        disabled={!canEdit}
                        onChange={e => updateRow(row.key, { state: e.target.value })}
                        onBlur={() => saveRow(row)}
                      >
                        <option value="">Select…</option>
                        {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </td>
                    <td style={{ minWidth: 130 }}>
                      <select
                        className="field-input"
                        value={row.registration_type}
                        disabled={!canEdit}
                        onChange={e => { updateRow(row.key, { registration_type: e.target.value }); }}
                        onBlur={() => saveRow(row)}
                      >
                        {GST_REGISTRATION_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </td>
                    <td style={{ minWidth: 160 }}>
                      <input
                        className="field-input"
                        value={row.place_of_business}
                        disabled={!canEdit}
                        onChange={e => updateRow(row.key, { place_of_business: e.target.value })}
                        onBlur={() => saveRow(row)}
                        placeholder="Hyderabad HO"
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
                        >
                          <i className="ti ti-trash" style={{ fontSize: 13 }} />
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {rows.length === 0 && (
            <div style={{ textAlign: "center", padding: "20px 0", color: "var(--on-variant)", fontSize: 13 }}>
              No GST registrations added yet.
            </div>
          )}
        </div>
      )}
      {canEdit && (
        <button type="button" className="btn btn-ghost btn-sm" style={{ marginTop: 12, color: "var(--primary)" }} onClick={addRow}>
          <i className="ti ti-plus" /> Add GSTIN
        </button>
      )}
    </ProfileCard>
  );
}
