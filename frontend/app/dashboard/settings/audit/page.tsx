"use client";

import { Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuditLog } from "@/hooks/useAuditLog";
import AuditFilters from "./_components/AuditFilters";
import AuditTable from "./_components/AuditTable";
import { rangeDates } from "./_components/auditView";
import { localISODate } from "@/app/dashboard/attendance/_components/monthView";

export default function AuditLogPage() {
  return (
    <Suspense fallback={null}>
      <AuditLogPageInner />
    </Suspense>
  );
}

// useSearchParams (reads ?module= for deep links, e.g. from Settings -> Birthday Wishes) requires a Suspense boundary around it for the
// production build: see AGENTS.md, this Next.js build is stricter here.
function AuditLogPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const todayISO = localISODate();
  const defaults = rangeDates("30d", todayISO);

  const { filters, applyFilters, page, setPage, data, loading, error } = useAuditLog({ module: searchParams.get("module") ?? "", search: "", dateFrom: defaults.from, dateTo: defaults.to });
  const isChanged = Boolean(filters.module || filters.search) || filters.dateFrom !== defaults.from || filters.dateTo !== defaults.to;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Audit Log</div>
          <div className="page-sub">Immutable record of all system actions across every module</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      <AuditFilters
        filters={filters} todayISO={todayISO} isChanged={isChanged} onChange={applyFilters}
        onClear={() => applyFilters({ module: "", search: "", dateFrom: defaults.from, dateTo: defaults.to })}
      />
      <AuditTable data={data} loading={loading} error={error} page={page} onPage={setPage} />
    </>
  );
}
