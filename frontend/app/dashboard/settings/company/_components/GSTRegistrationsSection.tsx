"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { GSTRegistration } from "@/types/company";
import GSTRegistrationsTable from "./GSTRegistrationsTable";
import GSTRegistrationModal from "./GSTRegistrationModal";

export default function GSTRegistrationsSection({ canEdit }: { canEdit: boolean }) {
  const { data, loading, error, refetch } =
    useFetch<{ results: GSTRegistration[] }>(`${API.settings.gstRegistrations.list}?page_size=100`);
  const [modalTarget, setModalTarget] = useState<GSTRegistration | "new" | null>(null);

  const registrations = data?.results ?? [];

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-receipt-tax" /> GST Registrations</div>
        {canEdit && (
          <button className="btn btn-filled btn-sm" onClick={() => setModalTarget("new")}>
            <i className="ti ti-plus" /> Add Registration
          </button>
        )}
      </div>

      {loading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>}
      {error && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}
      {!loading && !error && (
        <GSTRegistrationsTable
          registrations={registrations}
          canEdit={canEdit}
          onEdit={reg => setModalTarget(reg)}
          onChanged={refetch}
        />
      )}

      {modalTarget && (
        <GSTRegistrationModal
          existing={modalTarget === "new" ? null : modalTarget}
          onClose={() => setModalTarget(null)}
          onSaved={() => { setModalTarget(null); refetch(); }}
        />
      )}
    </div>
  );
}
