"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { Director } from "@/types/company";
import DirectorsTable from "./DirectorsTable";
import DirectorModal from "./DirectorModal";

export default function DirectorsSection({ canEdit }: { canEdit: boolean }) {
  const { data, loading, error, refetch } =
    useFetch<{ results: Director[] }>(`${API.settings.directors.list}?page_size=100`);
  const [modalTarget, setModalTarget] = useState<Director | "new" | null>(null);

  const directors = data?.results ?? [];

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-user-star" /> Directors</div>
        {canEdit && (
          <button className="btn btn-filled btn-sm" onClick={() => setModalTarget("new")}>
            <i className="ti ti-plus" /> Add Director
          </button>
        )}
      </div>

      {loading && <div style={{ padding: "40px 24px", textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>}
      {error && <div style={{ padding: "24px", color: "var(--error)", fontSize: 14 }}>{error}</div>}
      {!loading && !error && (
        <DirectorsTable
          directors={directors}
          canEdit={canEdit}
          onEdit={director => setModalTarget(director)}
          onChanged={refetch}
        />
      )}

      {modalTarget && (
        <DirectorModal
          existing={modalTarget === "new" ? null : modalTarget}
          onClose={() => setModalTarget(null)}
          onSaved={() => { setModalTarget(null); refetch(); }}
        />
      )}
    </div>
  );
}
