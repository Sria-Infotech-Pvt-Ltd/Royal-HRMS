"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { EducationExperienceFieldConfig, EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";

interface Props {
  canEdit: boolean;
}

// Show/require toggles only — no add/reorder/delete, since this is a fixed
// set of rows (see the backend model's own docstring for why). Level/
// Institution (education) and Employer/Designation (experience) aren't
// listed at all — they're the structural minimum identifying an entry,
// always shown and required, not configurable.
function Group({ title, rows, canEdit, busyId, onToggle }: {
  title: string;
  rows: EducationExperienceFieldConfig[];
  canEdit: boolean;
  busyId: string | null;
  onToggle: (row: EducationExperienceFieldConfig, key: "visible" | "required", value: boolean) => void;
}) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>{title}</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Field</th>
              <th style={{ textAlign: "center" }}>Visible</th>
              <th style={{ textAlign: "center" }}>Required</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(r => (
              <tr key={r.id}>
                <td style={{ fontWeight: 600, fontSize: 13 }}>{r.label}</td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={r.visible}
                    disabled={!canEdit || busyId === r.id}
                    onChange={e => onToggle(r, "visible", e.target.checked)}
                  />
                </td>
                <td style={{ textAlign: "center" }}>
                  <input
                    type="checkbox"
                    checked={r.required}
                    disabled={!canEdit || busyId === r.id || !r.visible}
                    title={!r.visible ? "Show the field first before requiring it" : undefined}
                    onChange={e => onToggle(r, "required", e.target.checked)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function EducationExperienceFieldConfigTable({ canEdit }: Props) {
  const { data, loading, error, refetch } = useFetch<EducationExperienceFieldConfigResponse>(
    API.onboarding.educationExperienceFieldConfig
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rowError, setRowError] = useState<string | null>(null);

  async function toggle(row: EducationExperienceFieldConfig, key: "visible" | "required", value: boolean) {
    setBusyId(row.id);
    setRowError(null);
    try {
      // Hiding a field that was required makes no sense to leave required —
      // clear it in the same request so the two never end up contradicting
      // each other.
      const body: Record<string, boolean> = { [key]: value };
      if (key === "visible" && !value) body.required = false;
      await clientApi.patch(API.onboarding.educationExperienceFieldConfigDetail(row.id), body);
      refetch();
    } catch (err: unknown) {
      setRowError((err as { message?: string })?.message ?? "Failed to update field.");
    } finally {
      setBusyId(null);
    }
  }

  if (loading) return <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading fields…</div>;
  if (error || !data) return <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error ?? "Failed to load."}</div>;

  return (
    <div style={{ padding: "20px 24px" }}>
      <p style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 0, marginBottom: 16 }}>
        Education and Experience are add/remove lists on the onboarding wizard — Type/Institution
        (Education) and Employer/Designation (Experience) always show since they identify the entry.
        Everything else below can be shown, hidden, or made required.
      </p>
      {rowError && (
        <div style={{ marginBottom: 16, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {rowError}
        </div>
      )}
      <Group title="Education" rows={data.education} canEdit={canEdit} busyId={busyId} onToggle={toggle} />
      <Group title="Experience" rows={data.experience} canEdit={canEdit} busyId={busyId} onToggle={toggle} />
    </div>
  );
}
