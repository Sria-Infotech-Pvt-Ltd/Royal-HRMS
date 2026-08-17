"use client";

import { useState } from "react";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { MODULE_LABELS } from "@/types/platformAdmin";
import type { Company } from "@/types/platformAdmin";

interface Props {
  companies: Company[];
  onChanged: () => void;
}

export default function CompaniesTable({ companies, onChanged }: Props) {
  const [togglingId, setTogglingId] = useState<string | null>(null);

  async function toggleActive(company: Company) {
    setTogglingId(company.id);
    try {
      await platformAdminApi.patch(API.platformAdmin.companies.detail(company.id), {
        is_active: !company.is_active,
      });
      onChanged();
    } finally {
      setTogglingId(null);
    }
  }

  if (companies.length === 0) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>No companies yet.</div>;
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Company</th>
            <th>Code</th>
            <th>Modules</th>
            <th>Status</th>
            <th>Created</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {companies.map(c => (
            <tr key={c.id}>
              <td>{c.company_name}</td>
              <td><span className="badge badge-neutral">{c.company_code}</span></td>
              <td style={{ maxWidth: 320 }}>
                {c.enabled_modules.length === 0
                  ? <span className="text-muted">None</span>
                  : c.enabled_modules.map(m => MODULE_LABELS[m] ?? m).join(", ")}
              </td>
              <td>
                <span className={`badge ${c.is_active ? "badge-success" : "badge-neutral"}`}>
                  {c.is_active ? "Active" : "Disabled"}
                </span>
              </td>
              <td>{new Date(c.created_at).toLocaleDateString()}</td>
              <td>
                <button
                  type="button"
                  className={`btn btn-sm ${c.is_active ? "btn-ghost" : "btn-outline"}`}
                  disabled={togglingId === c.id}
                  onClick={() => toggleActive(c)}
                  suppressHydrationWarning
                >
                  {togglingId === c.id ? "…" : c.is_active ? "Disable" : "Enable"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
