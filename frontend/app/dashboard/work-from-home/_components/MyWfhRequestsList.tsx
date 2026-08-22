"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { PaginatedResponse } from "@/app/dashboard/leave/_data";
import { WFH_STATUS_LABELS, type WorkFromHomeRequest } from "@/types/workFromHome";

const STATUS_BADGE: Record<WorkFromHomeRequest["status"], string> = {
  pending:    "badge-warn",
  l2_pending: "badge-info",
  approved:   "badge-success",
  rejected:   "badge-error",
  cancelled:  "badge-neutral",
};

function fmtDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function MyWfhRequestsList({ refreshKey }: { refreshKey: number }) {
  const { showToast } = useToast();
  const [cancellingId, setCancellingId] = useState<string | null>(null);
  const { data, loading, error, refetch } = useFetch<PaginatedResponse<WorkFromHomeRequest>>(
    `${API.workFromHome.requests}?page_size=50`,
  );
  const requests = data?.results ?? [];

  // refreshKey changes after a new submission — refetch to pick it up.
  // Guarded to skip the initial mount (refreshKey starts at 0) since
  // useFetch already fetches once on its own.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (refreshKey > 0) refetch(); }, [refreshKey]);

  async function cancel(id: string) {
    setCancellingId(id);
    try {
      await clientApi.patch(API.workFromHome.requestDetail(id));
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to cancel request.", "error");
    } finally {
      setCancellingId(null);
    }
  }

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-[13px] text-[var(--on-variant)]">
        <i className="ti ti-loader-2 animate-spin text-[22px]" style={{ color: "var(--primary)" }} />
        Loading your requests…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-[var(--outline-v)] p-10 text-center">
        <p className="text-sm text-[var(--on-variant)] mb-4">{error}</p>
        <button onClick={refetch} className="px-4 py-2 rounded-lg text-sm font-semibold text-white" style={{ background: "var(--primary)" }}>
          Try again
        </button>
      </div>
    );
  }

  if (requests.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-[var(--outline-v)] p-12 text-center">
        <i className="ti ti-home-2 text-4xl text-[var(--outline)] block mb-3" />
        <p className="text-sm text-[var(--on-variant)]">You haven&apos;t submitted any work-from-home requests yet.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {requests.map(req => (
        <div key={req.id} className="bg-white rounded-xl border border-[var(--outline-v)] p-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex-1 min-w-[220px]">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-[var(--on-bg)]">
                {fmtDate(req.start_date)} → {fmtDate(req.end_date)}
              </span>
              <span className={`badge ${STATUS_BADGE[req.status]}`}>{WFH_STATUS_LABELS[req.status]}</span>
            </div>
            {req.location_label && <div className="text-xs text-[var(--on-variant)]">{req.location_label}</div>}
            {req.reason && <div className="text-xs text-[var(--on-variant)] mt-1">{req.reason}</div>}
          </div>
          <div className="text-xs text-[var(--on-variant)] text-right min-w-[160px]">
            {req.l1_approver_name && <div>L1: {req.l1_approver_name}{req.l1_status ? ` (${req.l1_status})` : ""}</div>}
            {req.l2_approver_name && <div>L2: {req.l2_approver_name}{req.l2_status ? ` (${req.l2_status})` : ""}</div>}
          </div>
          {req.can_cancel && (
            <button
              onClick={() => cancel(req.id)}
              disabled={cancellingId === req.id}
              suppressHydrationWarning
              className="px-3.5 py-2 rounded-lg text-xs font-semibold border border-[var(--outline-v)] text-[var(--on-variant)] hover:bg-[var(--bg-low)] disabled:opacity-60"
            >
              {cancellingId === req.id ? "Cancelling…" : "Cancel"}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
