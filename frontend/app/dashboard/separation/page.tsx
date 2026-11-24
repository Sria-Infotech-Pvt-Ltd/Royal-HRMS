"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import { useT } from "@/hooks/useI18n";
import type { PaginatedResponse, SeparationRequest } from "@/types/separation";
import { useSeparationAccess } from "./_access";
import { toQuery } from "./_workflow";
import { countSeparations, statusGroup, type StatusGroup } from "./_view";
import SeparationSummary from "./_components/SeparationSummary";
import { SeparationStyles } from "./_components/separationStyles";
import SeparationTable from "./_components/SeparationTable";
import SeparationFormModal from "./_components/SeparationFormModal";
import ConfirmModal from "./_components/ConfirmModal";
import DecisionModal from "./_components/DecisionModal";

export default function SeparationPage() {
  const router = useRouter();
  const t = useT();
  const { showToast } = useToast();
  const access = useSeparationAccess();

  const [scope,       setScope]     = useState<"" | "team">("");
  const [employeeId,  setEmployeeId] = useState("");
  const [page,         setPage]     = useState(1);
  const [group,        setGroup]    = useState<"all" | StatusGroup>("all");

  const [showCreate, setShowCreate] = useState(false);
  const [editing,    setEditing]    = useState<SeparationRequest | null>(null);
  const [cancelling, setCancelling] = useState<SeparationRequest | null>(null);
  const [rejecting,  setRejecting]  = useState<SeparationRequest | null>(null);
  const [working,    setWorking]    = useState(false);

  const listUrl = `${API.separation.list}${toQuery({
    page, page_size: 20, scope, employee_id: employeeId.trim(),
  })}`;
  const { data, loading, error, refetch } = useFetch<PaginatedResponse<SeparationRequest>>(listUrl);
  const allRows = data?.results ?? [];
  const counts = countSeparations(allRows);
  // The status chips narrow the page already loaded; the server still decides what you may see at all.
  const rows = group === "all" ? allRows : allRows.filter(row => statusGroup(row.status) === group);

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function handleCancelConfirm() {
    if (!cancelling) return;
    setWorking(true);
    try {
      await clientApi.patch(API.separation.detail(cancelling.id), { action: "cancel" });
      showToast(t("Separation request cancelled."), "success");
      setCancelling(null);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, t("Failed to cancel the request.")), "error");
    } finally {
      setWorking(false);
    }
  }

  async function handleRejectConfirm(reason: string) {
    if (!rejecting) return;
    setWorking(true);
    try {
      // UAT-018 — this used to be clientApi.delete(...), which permanently
      // removed the row (no reason captured, request_number freed up for
      // reuse). This now does the same status-only change the per-stage
      // approval decision does, just reachable directly from the list.
      await clientApi.patch(API.separation.detail(rejecting.id), { action: "reject", reason });
      showToast(t("Separation request rejected."), "success");
      setRejecting(null);
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, t("Failed to reject the request.")), "error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Separation & Exit")}</div>
          <div className="page-sub">
            {scope === "team" ? t("Requests you can act on") : t("Your separation requests")}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowCreate(true)} suppressHydrationWarning>
            <i className="ti ti-plus" /> {t("Request Separation")}
          </button>
        </div>
      </div>

      <SeparationStyles />
      {!loading && <SeparationSummary counts={counts} isTeam={scope === "team"} />}

      <div className="sp-bar">
        {access.canApprove && (
          <div className="sp-seg" role="group" aria-label={t("Whose requests")}>
            <button type="button" className={scope === "" ? "is-on" : ""} aria-pressed={scope === ""} onClick={() => { setScope(""); setPage(1); }} suppressHydrationWarning>{t("My Requests")}</button>
            <button type="button" className={scope === "team" ? "is-on" : ""} aria-pressed={scope === "team"} onClick={() => { setScope("team"); setPage(1); }} suppressHydrationWarning>{t("Team Requests")}</button>
          </div>
        )}

        {([
          { key: "all" as const, label: "All", count: counts.all },
          { key: "waiting" as const, label: "Waiting", count: counts.waiting },
          { key: "approved" as const, label: "Approved", count: counts.approved },
          { key: "closed" as const, label: "Closed", count: counts.closed },
        ]).map(chip => (
          <button key={chip.key} type="button" className={`sp-chip${group === chip.key ? " is-on" : ""}`} aria-pressed={group === chip.key} onClick={() => setGroup(chip.key)}>
            {t(chip.label)} <small>{chip.count}</small>
          </button>
        ))}

        {(access.canPickEmployee || access.canApprove) && (
          <div className="sp-find" style={{ marginLeft: "auto" }}>
            <i className="ti ti-search" />
            <input
              placeholder={t("Filter by employee code…")}
              aria-label={t("Filter by employee code")}
              value={employeeId}
              onChange={e => { setEmployeeId(e.target.value); setPage(1); }}
              suppressHydrationWarning
            />
          </div>
        )}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        {loading ? (
          <div style={{ padding: "48px 20px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" /> {t("Loading…")}
          </div>
        ) : (
          <SeparationTable
            requests={rows}
            onView={r => router.push(`/dashboard/separation/${r.id}`)}
            onEdit={r => setEditing(r)}
            onCancel={r => setCancelling(r)}
            onReject={r => setRejecting(r)}
            onRequest={() => setShowCreate(true)}
            isFiltered={group !== "all" || employeeId.trim() !== "" || scope === "team"}
          />
        )}

        {data && data.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{t("Page {page} of {total}", { page: data.page, total: data.total_pages })}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))} suppressHydrationWarning>
                <i className="ti ti-chevron-left" /> {t("Prev")}
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => setPage(p => Math.min(p + 1, data.total_pages))} suppressHydrationWarning>
                {t("Next")} <i className="ti ti-chevron-right" />
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
          onSaved={() => { setShowCreate(false); showToast(t("Separation request submitted."), "success"); refetch(); }}
        />
      )}

      {editing && (
        <SeparationFormModal
          mode="edit"
          existing={editing}
          canPickEmployee={access.canPickEmployee}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); showToast(t("Separation request updated."), "success"); refetch(); }}
        />
      )}

      {cancelling && (
        <ConfirmModal
          title={t("Cancel Separation Request")}
          body={t("This will cancel the separation request for {name}. This cannot be undone.", { name: cancelling.employee_name })}
          confirmLabel={t("Yes, Cancel Request")}
          danger
          saving={working}
          onConfirm={handleCancelConfirm}
          onCancel={() => setCancelling(null)}
        />
      )}

      {rejecting && (
        <DecisionModal
          action="reject"
          employeeName={rejecting.employee_name}
          saving={working}
          onConfirm={handleRejectConfirm}
          onClose={() => setRejecting(null)}
        />
      )}
    </div>
  );
}
