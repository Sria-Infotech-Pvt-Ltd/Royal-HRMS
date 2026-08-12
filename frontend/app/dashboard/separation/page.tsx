"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import type { PaginatedResponse, SeparationLookupOption, SeparationRequest } from "@/types/separation";
import { useSeparationAccess } from "./_access";
import { toQuery } from "./_workflow";
import SeparationTable from "./_components/SeparationTable";
import SeparationFormModal from "./_components/SeparationFormModal";
import ConfirmModal from "./_components/ConfirmModal";

export default function SeparationPage() {
  const router = useRouter();
  const { showToast } = useToast();
  const access = useSeparationAccess();

  const { data: types } = useFetch<SeparationLookupOption[]>(API.separation.types);

  const [typeFilter, setTypeFilter] = useState("");
  const [scope,       setScope]     = useState<"" | "team">("");
  const [employeeId,  setEmployeeId] = useState("");
  const [page,         setPage]     = useState(1);

  const [showCreate, setShowCreate] = useState(false);
  const [editing,    setEditing]    = useState<SeparationRequest | null>(null);
  const [cancelling, setCancelling] = useState<SeparationRequest | null>(null);
  const [deleting,   setDeleting]   = useState<SeparationRequest | null>(null);
  const [working,    setWorking]    = useState(false);

  const listUrl = `${API.separation.list}${toQuery({
    page, page_size: 20, separation_type: typeFilter, scope, employee_id: employeeId.trim(),
  })}`;
  const { data, loading, error, refetch } = useFetch<PaginatedResponse<SeparationRequest>>(listUrl);
  const rows = data?.results ?? [];

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function handleCancelConfirm() {
    if (!cancelling) return;
    setWorking(true);
    try {
      await clientApi.patch(API.separation.detail(cancelling.id), { action: "cancel" });
      showToast("Separation request cancelled.", "success");
      setCancelling(null);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to cancel the request."), "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleDeleteConfirm() {
    if (!deleting) return;
    setWorking(true);
    try {
      await clientApi.delete(API.separation.detail(deleting.id));
      showToast("Separation request deleted.", "success");
      setDeleting(null);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, "Failed to delete the request."), "error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Separation & Exit</div>
          <div className="page-sub">
            {scope === "team" ? "Requests you can act on" : "Your separation requests"}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowCreate(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> Request Separation
          </button>
        </div>
      </div>

      <div className="flex items-center gap-3 flex-wrap mb-4">
        {access.canApprove && (
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className={`btn btn-sm ${scope === "" ? "btn-filled" : "btn-outline"}`}
              onClick={() => { setScope(""); setPage(1); }} suppressHydrationWarning
            >
              My Requests
            </button>
            <button
              className={`btn btn-sm ${scope === "team" ? "btn-filled" : "btn-outline"}`}
              onClick={() => { setScope("team"); setPage(1); }} suppressHydrationWarning
            >
              Team Requests
            </button>
          </div>
        )}

        <select
          className="field-input field-select" style={{ width: 180 }} value={typeFilter}
          onChange={e => { setTypeFilter(e.target.value); setPage(1); }}
        >
          <option value="">All Types</option>
          {(types ?? []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>

        {(access.canPickEmployee || access.canApprove) && (
          <input
            className="field-input" style={{ width: 200 }}
            placeholder="Filter by employee code…"
            value={employeeId}
            onChange={e => { setEmployeeId(e.target.value); setPage(1); }}
            suppressHydrationWarning
          />
        )}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        {loading ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" /> Loading…
          </div>
        ) : (
          <SeparationTable
            requests={rows}
            onView={r => router.push(`/dashboard/separation/${r.id}`)}
            onEdit={r => setEditing(r)}
            onCancel={r => setCancelling(r)}
            onDelete={r => setDeleting(r)}
          />
        )}

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {data.page} of {data.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))} suppressHydrationWarning>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))} suppressHydrationWarning>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {showCreate && (
        <SeparationFormModal
          mode="create"
          canPickEmployee={access.canPickEmployee}
          onClose={() => setShowCreate(false)}
          onSaved={() => { setShowCreate(false); showToast("Separation request submitted.", "success"); refetch(); }}
        />
      )}

      {editing && (
        <SeparationFormModal
          mode="edit"
          existing={editing}
          canPickEmployee={access.canPickEmployee}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); showToast("Separation request updated.", "success"); refetch(); }}
        />
      )}

      {cancelling && (
        <ConfirmModal
          title="Cancel Separation Request"
          body={`This will cancel the separation request for ${cancelling.employee_name}. This cannot be undone.`}
          confirmLabel="Yes, Cancel Request"
          danger
          saving={working}
          onConfirm={handleCancelConfirm}
          onCancel={() => setCancelling(null)}
        />
      )}

      {deleting && (
        <ConfirmModal
          title="Delete Separation Request"
          body={`This will permanently delete the separation request for ${deleting.employee_name}.`}
          confirmLabel="Yes, Delete"
          danger
          saving={working}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}
