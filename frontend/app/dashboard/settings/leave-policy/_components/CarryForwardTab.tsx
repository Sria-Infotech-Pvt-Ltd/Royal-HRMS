"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import type {
  CarryForwardYearsResponse,
  CarryForwardPreviewResponse,
  CarryForwardHistoryResponse,
  CarryForwardLog,
} from "@/types/leave";
import CarryForwardPreviewTable from "./CarryForwardPreviewTable";
import CarryForwardHistoryTable from "./CarryForwardHistoryTable";
import CarryForwardRunModal from "./CarryForwardRunModal";

const HISTORY_PAGE_SIZE = 20;

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function CarryForwardTab() {
  const user = useCurrentUser();
  const canManageLeave = usePermission("leave.edit");
  const { showToast } = useToast();

  const { data: years, loading: yearsLoading, error: yearsError } = useFetch<CarryForwardYearsResponse>(API.leave.carryForward.years);

  const [fromYear, setFromYear] = useState<number | null>(null);
  const [toYear,   setToYear]   = useState<number | null>(null);

  const [preview,       setPreview]       = useState<CarryForwardPreviewResponse | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError,  setPreviewError]  = useState<string | null>(null);

  const [showRunModal,  setShowRunModal]  = useState(false);
  const [running,       setRunning]       = useState(false);
  const [runError,      setRunError]      = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  const [historyPage, setHistoryPage] = useState(1);
  const {
    data: history, loading: historyLoading, refetch: refetchHistory,
  } = useFetch<CarryForwardHistoryResponse>(
    `${API.leave.carryForward.history}?page=${historyPage}&page_size=${HISTORY_PAGE_SIZE}`
  );

  useEffect(() => {
    if (years && fromYear === null && toYear === null) {
      setFromYear(years.default_from);
      setToYear(years.default_to);
    }
  }, [years, fromYear, toYear]);

  // Selecting a different period invalidates whatever was previewed before.
  useEffect(() => {
    setPreview(null);
    setPreviewError(null);
    setDuplicateWarning(null);
  }, [fromYear, toYear]);

  if (!user) return null;
  if (!canManageLeave) {
    return (
      <div className="empty-state">
        <i className="ti ti-lock" />
        <h3>Access Denied</h3>
        <p>You do not have permission to view carry-forward operations.</p>
      </div>
    );
  }

  const fromYearOptions = Array.from(new Set((years?.years ?? []).map(y => y.from_year))).sort((a, b) => a - b);
  const toYearOptions   = Array.from(new Set((years?.years ?? []).map(y => y.to_year)))
    .filter(y => fromYear === null || y > fromYear)
    .sort((a, b) => a - b);

  const busy = previewLoading || running;
  const noYearsAvailable = !yearsLoading && !yearsError && fromYearOptions.length === 0;

  async function runPreview() {
    if (fromYear === null || toYear === null) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const res = await clientApi.post<{ data: CarryForwardPreviewResponse }>(
        API.leave.carryForward.preview,
        { from_year: fromYear, to_year: toYear }
      );
      setPreview(res.data.data);
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      setPreviewError(e.message ?? "Failed to load carry-forward preview.");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function confirmRun() {
    if (fromYear === null || toYear === null) return;
    setRunning(true);
    setRunError(null);
    try {
      const res = await clientApi.post<{ data: CarryForwardLog }>(
        API.leave.carryForward.run,
        { from_year: fromYear, to_year: toYear }
      );
      const result = res.data.data;
      showToast(`Carry forward completed. ${result.total_processed} processed, ${result.total_skipped} skipped.`, "success");
      setShowRunModal(false);
      setDuplicateWarning(null);
      refetchHistory();
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      if (e.status === 409) {
        setShowRunModal(false);
        setDuplicateWarning(e.message ?? "This period has already been executed. Select a different year range or check the history below.");
      } else if (e.status === 400) {
        setShowRunModal(false);
        setRunError(e.message ?? "Invalid year selection.");
      } else {
        setShowRunModal(false);
        showToast("Something went wrong. Please try again.", "error");
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="scope-banner flex items-center gap-4 flex-wrap">
        <i className="ti ti-repeat text-[22px] text-[var(--primary)] flex-shrink-0" />
        <div className="flex-1 min-w-[240px]">
          <div className="text-[13px] font-semibold text-[var(--on-bg)]">Carry Forward Unused Leave</div>
          <div className="text-xs text-[var(--on-variant)] mt-0.5">
            Select a year range, preview what will happen, then run to carry forward unused leave balances into the next year.
          </div>
        </div>
      </div>

      {yearsError ? (
        <div className="card mb-20" style={{ padding: "20px 24px", color: "var(--error)", fontSize: 13 }}>
          {yearsError} — unable to load available year pairs.
        </div>
      ) : noYearsAvailable ? (
        <div className="empty-state">
          <i className="ti ti-calendar-off" />
          <h3>No leave year data found</h3>
          <p>Employees must have leave balances recorded before carry-forward can be run.</p>
        </div>
      ) : (
        <div className="card mb-20">
          <div style={{ padding: "20px 24px", display: "flex", alignItems: "flex-end", gap: 16, flexWrap: "wrap" }}>
            {yearsLoading ? (
              <div style={{ color: "var(--on-variant)", fontSize: 13 }}><Spin /> &nbsp;Loading year options…</div>
            ) : (
              <>
                <div className="field-group" style={{ marginBottom: 0, width: 160 }}>
                  <label className="field-label">From Year</label>
                  <select
                    className="field-input field-select"
                    value={fromYear ?? ""}
                    onChange={e => setFromYear(Number(e.target.value))}
                  >
                    {fromYearOptions.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
                <div className="field-group" style={{ marginBottom: 0, width: 160 }}>
                  <label className="field-label">To Year</label>
                  <select
                    className="field-input field-select"
                    value={toYear ?? ""}
                    onChange={e => setToYear(Number(e.target.value))}
                  >
                    {toYearOptions.map(y => <option key={y} value={y}>{y}</option>)}
                  </select>
                </div>
                <button className="btn btn-ghost" onClick={runPreview} disabled={busy || fromYear === null || toYear === null}>
                  {previewLoading ? <><Spin />&nbsp;Previewing…</> : <><i className="ti ti-eye" /> Preview</>}
                </button>
                <button
                  className="btn btn-filled"
                  style={{ background: "var(--error-solid)" }}
                  onClick={() => { setRunError(null); setShowRunModal(true); }}
                  disabled={busy || fromYear === null || toYear === null}
                >
                  <i className="ti ti-player-play" /> Run Carry Forward
                </button>
              </>
            )}
          </div>

          {previewError && (
            <div style={{ margin: "0 24px 20px", padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
              {previewError}
            </div>
          )}
          {runError && (
            <div style={{ margin: "0 24px 20px", padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
              {runError}
            </div>
          )}
        </div>
      )}

      {duplicateWarning && (
        <div className="mb-20" style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "14px 18px", background: "rgba(162,98,12,0.08)", border: "1px solid rgba(162,98,12,0.3)", borderRadius: "var(--radius)", color: "var(--warn)" }}>
          <i className="ti ti-alert-triangle" style={{ fontSize: 18, flexShrink: 0, marginTop: 1 }} />
          <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>{duplicateWarning}</div>
          <button className="btn btn-ghost btn-sm" onClick={() => setDuplicateWarning(null)} style={{ flexShrink: 0 }}>
            <i className="ti ti-x" />
          </button>
        </div>
      )}

      {preview && <CarryForwardPreviewTable preview={preview} />}

      <CarryForwardHistoryTable
        history={history}
        loading={historyLoading}
        page={historyPage}
        onPageChange={setHistoryPage}
      />

      {showRunModal && fromYear !== null && toYear !== null && (
        <CarryForwardRunModal
          fromYear={fromYear}
          toYear={toYear}
          pendingCount={preview && preview.from_year === fromYear && preview.to_year === toYear ? preview.pending_count : null}
          running={running}
          onConfirm={confirmRun}
          onClose={() => setShowRunModal(false)}
        />
      )}
    </>
  );
}
