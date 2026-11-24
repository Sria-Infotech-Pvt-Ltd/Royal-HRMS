"use client";

import Link from "next/link";
import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PaginatedResponse, SeparationRequest } from "@/types/separation";
import { statusBadgeClass, fmtDate } from "@/app/dashboard/separation/_workflow";
import SeparationFormModal from "@/app/dashboard/separation/_components/SeparationFormModal";
import { useT } from "@/hooks/useI18n";

/** "Separation" action card on the employee's own Profile page — creates a
 *  self-service request (no employee picker; always files for the viewer)
 *  or summarizes their most recent one. See app/dashboard/separation/ for
 *  the full list/detail views. */
export default function SeparationCard() {
  const t = useT();
  const [showForm, setShowForm] = useState(false);
  const { data, loading, refetch } = useFetch<PaginatedResponse<SeparationRequest>>(`${API.separation.list}?page_size=5`);
  const requests = data?.results ?? [];
  const active = requests.find(r => r.can_cancel) ?? requests[0];

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-logout" />{t("Separation")}</span>
      </div>
      <div className="card-body">
        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> {t("Loading…")}</p>
        ) : !active ? (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
            <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}>
              {t("You don't have an active separation request.")}
            </p>
            <button className="btn btn-outline btn-sm" onClick={() => setShowForm(true)} suppressHydrationWarning>
              <i className="ti ti-plus" /> {t("Create Separation Request")}
            </button>
          </div>
        ) : (
          <>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">{t("Separation Type")}</label>
                <input className="field-input" value={active.separation_type_display} disabled />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Request Date")}</label>
                <input className="field-input" value={fmtDate(active.request_date)} disabled />
              </div>
            </div>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">{t("Proposed Last Working Day")}</label>
                <input className="field-input" value={fmtDate(active.proposed_last_working_day)} disabled />
              </div>
              <div className="field-group">
                <label className="field-label">{t("Status")}</label>
                <div style={{ paddingTop: 6 }}>
                  <span className={`badge ${statusBadgeClass(active.status)}`}>{active.status_display}</span>
                </div>
              </div>
            </div>
            <Link href={`/dashboard/separation/${active.id}`} className="btn btn-ghost btn-sm">
              <i className="ti ti-eye" /> {t("View Request")}
            </Link>
          </>
        )}
      </div>

      {showForm && (
        <SeparationFormModal
          mode="create"
          canPickEmployee={false}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); refetch(); }}
        />
      )}
    </div>
  );
}
