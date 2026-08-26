"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { GSTRegistration } from "@/types/company";

interface Props {
  registrations: GSTRegistration[];
  canEdit: boolean;
  onEdit: (reg: GSTRegistration) => void;
  onChanged: () => void;
}

export default function GSTRegistrationsTable({ registrations, canEdit, onEdit, onChanged }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function remove(reg: GSTRegistration) {
    if (!window.confirm(`Remove the GST registration for ${reg.state} (${reg.gstin})?`)) return;
    setBusyId(reg.id);
    setRowError(null);
    try {
      await clientApi.delete(API.settings.gstRegistrations.detail(reg.id));
      onChanged();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to remove GST registration.");
    } finally {
      setBusyId(null);
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
              <th>State</th>
              <th>GSTIN</th>
              <th>Type</th>
              <th>Place of Business</th>
              <th style={{ textAlign: "center" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {registrations.map(reg => (
              <tr key={reg.id}>
                <td>{reg.state}</td>
                <td style={{ fontFamily: "monospace" }}>{reg.gstin}</td>
                <td style={{ textTransform: "capitalize" }}>{reg.registration_type}</td>
                <td>{reg.place_of_business || "—"}</td>
                <td style={{ textAlign: "center" }}>
                  <div style={{ display: "flex", gap: 6, justifyContent: "center" }}>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6 }}
                      onClick={() => onEdit(reg)}
                      disabled={!canEdit || busyId === reg.id}
                      title="Edit"
                    >
                      <i className="ti ti-pencil" style={{ fontSize: 13 }} />
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ width: 28, height: 28, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)" }}
                      onClick={() => remove(reg)}
                      disabled={!canEdit || busyId === reg.id}
                      title="Remove"
                    >
                      <i className="ti ti-trash" style={{ fontSize: 13 }} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {registrations.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", padding: "32px 0", color: "var(--on-variant)" }}>
                  No GST registrations added yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
