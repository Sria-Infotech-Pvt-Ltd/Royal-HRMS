"use client";

import { useCallback, useState, type CSSProperties } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import type { PayrollCycle } from "@/types/payroll";

interface PagedResponse<T> { results: T[]; count: number; }
interface Branch { id: string; branch_name: string; branch_code: string; }

// Same eligibility rule the existing ECR download (payroll/runs/[id]) already
// enforces server-side — mirrored here only to enable/disable the button and
// show a clear reason, not to duplicate any business logic.
const ECR_READY_STATUSES = ["payslips_generated", "query_window_open", "paid", "closed"];

type EcrFormat = "xlsx" | "pdf" | "txt";

// Same chevron artwork as .field-select in globals.css — these two selects
// sit inside a transparent/borderless .search-bar pill (their own icon
// already leads the pill), so they can't just take the .field-select class
// (its border/background would fight the pill's own styling); reproduced
// as inline style instead, explicitly via backgroundColor rather than the
// `background` shorthand so it doesn't reset backgroundImage back to none.
const SEARCH_BAR_SELECT_STYLE: CSSProperties = {
  border: "none",
  backgroundColor: "transparent",
  color: "var(--on-bg)",
  fontSize: 13,
  appearance: "none",
  WebkitAppearance: "none",
  MozAppearance: "none",
  backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>\")",
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 0 center",
  backgroundSize: "15px",
  paddingRight: 22,
  cursor: "pointer",
};

export default function PayrollReports() {
  const [selectedCycle, setSelectedCycle] = useState<string>("");
  const [selectedBranch, setSelectedBranch] = useState<string>("");
  const [downloadingFormat, setDownloadingFormat] = useState<EcrFormat | null>(null);
  const [dlError, setDlError] = useState<string | null>(null);

  const { data: cyclesPage } = useFetch<PagedResponse<PayrollCycle>>(API.payroll.cycles);
  const { data: branchPage  } = useFetch<PagedResponse<Branch>>(API.branches.list);

  const cycles   = cyclesPage?.results ?? [];
  const branches = branchPage?.results ?? [];

  const paidCycles = cycles.filter(c => ECR_READY_STATUSES.includes(c.status));
  const cycle = cycles.find(c => c.id === selectedCycle);
  const canDownloadEcr = !!cycle && ECR_READY_STATUSES.includes(cycle.status);

  // Same download mechanics as the existing ECR button on the payroll run
  // detail page (payroll/runs/[id]/page.tsx) — same blob handling, same
  // filename pattern — now shared by both formats, since the backend
  // exposes the Excel and PDF ECR files as two sibling endpoints returning
  // the same kind of file blob.
  const downloadEcr = useCallback(async (format: EcrFormat) => {
    if (!cycle) return;
    setDownloadingFormat(format);
    setDlError(null);
    try {
      const url = format === "pdf" ? API.payroll.cycleEcrPdf(cycle.id)
        : format === "txt" ? API.payroll.cycleEcrText(cycle.id)
        : API.payroll.cycleEcr(cycle.id);
      const response = await clientApi.get(url, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href  = blobUrl;
      const per    = new Date(cycle.cycle_start).toLocaleDateString("en-IN", { month: "short", year: "numeric" }).replace(" ", "_");
      const branch = (cycle.branch_name ?? "All").replace(/ /g, "_");
      link.download = `ECR_${per}_${branch}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(blobUrl);
    } catch (err: unknown) {
      // responseType: "blob" means an error response's JSON body arrives as
      // a Blob too — read as text and parsed manually to surface e.g. the
      // text export's "employees have no UAN on file" validation message.
      const blob = (err as { response?: { data?: Blob } })?.response?.data;
      let msg: string | undefined;
      if (blob instanceof Blob) {
        try {
          const parsed = JSON.parse(await blob.text());
          msg = parsed?.message;
        } catch { /* non-JSON error body — fall through to the generic message */ }
      }
      const formatLabel = format === "pdf" ? "PDF" : format === "txt" ? "text file" : "Excel";
      setDlError(msg || `Failed to download ECR ${formatLabel}. Please try again.`);
    } finally {
      setDownloadingFormat(null);
    }
  }, [cycle]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

      {/* Filter bar */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-calendar" />
          <select
            value={selectedCycle}
            onChange={e => setSelectedCycle(e.target.value)}
            style={SEARCH_BAR_SELECT_STYLE}
          >
            <option value="">All Periods</option>
            {cycles.map(c => (
              <option key={c.id} value={c.id}>
                {new Date(c.cycle_start).toLocaleString("en-IN", { month: "long", year: "numeric" })}
              </option>
            ))}
          </select>
        </div>

        <div className="search-bar" style={{ flex: "none" }}>
          <i className="ti ti-building-skyscraper" />
          <select
            value={selectedBranch}
            onChange={e => setSelectedBranch(e.target.value)}
            style={SEARCH_BAR_SELECT_STYLE}
          >
            <option value="">All Company Codes</option>
            {branches.map(b => (
              <option key={b.id} value={b.id}>{b.branch_name}</option>
            ))}
          </select>
        </div>

        <div style={{ flex: 1 }} />
      </div>

      {/* No paid cycles warning */}
      {paidCycles.length === 0 && cycles.length > 0 && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <span>ECR export is available after a payroll cycle is completed and payslips are dispatched. Complete a payroll run first.</span>
        </div>
      )}

      {cycles.length === 0 && (
        <div className="alert alert-info">
          <i className="ti ti-info-circle" />
          <span>No payroll cycles yet. Run your first payroll to enable ECR export.</span>
        </div>
      )}

      {dlError && (
        <div className="alert alert-error">
          <i className="ti ti-alert-circle" />
          <span>{dlError}</span>
        </div>
      )}

      {/* ECR Export */}
      <div className="card" style={{ maxWidth: 560 }}>
        <div style={{ padding: "16px 20px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 14 }}>
            <div style={{ width: 40, height: 40, borderRadius: "var(--radius)", background: "rgba(30,78,140,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <i className="ti ti-building-bank" style={{ fontSize: 20, color: "var(--primary)" }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600, marginBottom: 4 }}>ECR (Electronic Challan-cum-Return)</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", lineHeight: 1.5, marginBottom: 12 }}>
                Export ECR file for EPFO submission
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={!canDownloadEcr || downloadingFormat !== null}
                  onClick={() => downloadEcr("pdf")}
                  title={
                    !cycle ? "Select a period to export."
                    : !canDownloadEcr ? "ECR is only available once payslips have been generated for this period."
                    : undefined
                  }
                >
                  {downloadingFormat === "pdf"
                    ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Exporting…</>
                    : <><i className="ti ti-file-type-pdf" /> Export PDF</>}
                </button>
                <button
                  className="btn btn-filled btn-sm"
                  disabled={!canDownloadEcr || downloadingFormat !== null}
                  onClick={() => downloadEcr("xlsx")}
                  title={
                    !cycle ? "Select a period to export."
                    : !canDownloadEcr ? "ECR is only available once payslips have been generated for this period."
                    : undefined
                  }
                >
                  {downloadingFormat === "xlsx"
                    ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Exporting…</>
                    : <><i className="ti ti-table-export" /> Export Excel</>}
                </button>
                <button
                  className="btn btn-ghost btn-sm"
                  disabled={!canDownloadEcr || downloadingFormat !== null}
                  onClick={() => downloadEcr("txt")}
                  title={
                    !cycle ? "Select a period to export."
                    : !canDownloadEcr ? "ECR is only available once payslips have been generated for this period."
                    : "EPFO Unified Portal ECR upload file (#~# delimited .txt)"
                  }
                >
                  {downloadingFormat === "txt"
                    ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Exporting…</>
                    : <><i className="ti ti-file-text" /> Export Text (EPFO Upload)</>}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
