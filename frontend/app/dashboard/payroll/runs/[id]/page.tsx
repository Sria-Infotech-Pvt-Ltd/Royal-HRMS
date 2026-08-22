"use client";

import { use, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, EmployeePayslip } from "@/types/payroll";

const STATUS_LABEL: Record<string, string> = {
  draft:                "Draft",
  attendance_pending:   "Attendance Pending",
  attendance_approved:  "Attendance Approved",
  processing:           "Processing",
  payslips_generated:   "Payslips Generated",
  query_window_open:    "Query Window Open",
  paid:                 "Paid",
  closed:               "Closed",
  cancelled:            "Cancelled",
};

const STATUS_COLOR: Record<string, string> = {
  paid:   "#16a34a",
  closed: "#1d4ed8",
  cancelled: "#dc2626",
};

function fmt(n: string | number | undefined) {
  const num = typeof n === "string" ? parseFloat(n) : (n ?? 0);
  return isNaN(num) ? "₹0" : `₹${Math.round(num).toLocaleString("en-IN")}`;
}

function fmtDate(d: string | null | undefined) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function period(cycle: PayrollCycle) {
  return new Date(cycle.cycle_start).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

interface PaginatedPayslips { results: EmployeePayslip[]; count: number; }

const ECR_ELIGIBLE_STATUSES = ["payslips_generated", "query_window_open", "paid", "closed"];

export default function PayrollRunDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id }  = use(params);
  const router  = useRouter();
  const [downloading, setDownloading] = useState(false);
  const [dlError,     setDlError]     = useState<string | null>(null);
  const [missingEsi,  setMissingEsi]  = useState<{ employee_name: string; employee_code: string }[] | null>(null);

  const { data: cycle,    loading: loadCycle } = useFetch<PayrollCycle>(API.payroll.cycle(id));
  const { data: psData,   loading: loadPs    } = useFetch<PaginatedPayslips>(
    `${API.payroll.cyclePayslips(id)}?page_size=500`,
  );

  const canDownloadEcr = !!cycle && ECR_ELIGIBLE_STATUSES.includes(cycle.status);

  const payslips = psData?.results ?? [];
  const payslipsTruncated = psData != null && psData.count > payslips.length;

  const totalGross      = payslips.reduce((s, p) => s + parseFloat(p.gross_earnings  || "0"), 0);
  const totalDeductions = payslips.reduce((s, p) => s + parseFloat(p.total_deductions || "0"), 0);
  const totalNet        = payslips.reduce((s, p) => s + parseFloat(p.net_pay          || "0"), 0);
  const totalPF         = payslips.reduce((s, p) => s + parseFloat(p.pf_employee     || "0"), 0);

  const downloadEcr = useCallback(async () => {
    if (!cycle) return;
    setDownloading(true);
    setDlError(null);
    setMissingEsi(null);
    try {
      const response = await clientApi.get(API.payroll.cycleEcr(id), { responseType: "blob" });
      const url  = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href  = url;
      const per  = new Date(cycle.cycle_start).toLocaleDateString("en-IN", { month: "short", year: "numeric" }).replace(" ", "_");
      const branch = (cycle.branch_name ?? "All").replace(/ /g, "_");
      link.download = `ECR_${per}_${branch}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch {
      setDlError("Failed to download ECR. Please try again.");
    } finally {
      setDownloading(false);
    }
  }, [cycle, id]);

  const [downloadingText, setDownloadingText] = useState(false);

  const downloadEcrText = useCallback(async () => {
    if (!cycle) return;
    setDownloadingText(true);
    setDlError(null);
    setMissingEsi(null);
    try {
      const response = await clientApi.get(API.payroll.cycleEcrText(id), { responseType: "blob" });
      const url  = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href  = url;
      const per  = new Date(cycle.cycle_start).toLocaleDateString("en-IN", { month: "short", year: "numeric" }).replace(" ", "_");
      const branch = (cycle.branch_name ?? "All").replace(/ /g, "_");
      link.download = `ECR_${per}_${branch}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      // responseType: "blob" means an error response's JSON body arrives as
      // a Blob too, not parsed data — has to be read as text and parsed
      // manually to surface e.g. the "employees have no UAN on file" message.
      const blob = (err as { response?: { data?: Blob } })?.response?.data;
      let msg: string | undefined;
      if (blob instanceof Blob) {
        try {
          const parsed = JSON.parse(await blob.text());
          msg = parsed?.message;
        } catch { /* non-JSON error body — fall through to the generic message */ }
      }
      setDlError(msg || "Failed to download the ECR text file. Please try again.");
    } finally {
      setDownloadingText(false);
    }
  }, [cycle, id]);

  const [downloadingEsic, setDownloadingEsic] = useState(false);

  const downloadEsic = useCallback(async () => {
    if (!cycle) return;
    setDownloadingEsic(true);
    setDlError(null);
    setMissingEsi(null);
    try {
      const response = await clientApi.get(API.payroll.cycleEsic(id), { responseType: "blob" });
      const url  = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href  = url;
      const per  = new Date(cycle.cycle_start).toLocaleDateString("en-IN", { month: "2-digit", year: "numeric" }).replace("/", "_");
      link.download = `ESIC_Challan_${per}.xlsx`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      // responseType: "blob" means an error response's JSON body arrives as
      // a Blob too — read as text and parsed manually to surface e.g. the
      // "no ESI number on file" validation message.
      const blob = (err as { response?: { data?: Blob } })?.response?.data;
      let msg: string | undefined;
      let missing: { employee_name: string; employee_code: string }[] | undefined;
      if (blob instanceof Blob) {
        try {
          const parsed = JSON.parse(await blob.text());
          msg = parsed?.message;
          missing = parsed?.data?.missing_esi_number;
        } catch { /* non-JSON error body — fall through to the generic message */ }
      }
      if (missing && missing.length > 0) {
        // Structured list takes over the display entirely — the plain
        // sentence version of this same message is redundant once we can
        // show each employee as a clickable link to go fix it directly.
        setMissingEsi(missing);
      } else {
        setDlError(msg || "Failed to download the ESIC Challan. Please try again.");
      }
    } finally {
      setDownloadingEsic(false);
    }
  }, [cycle, id]);

  if (loadCycle) {
    return (
      <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2 spin" style={{ fontSize: 24 }} />
        <div style={{ marginTop: 10, fontSize: 14 }}>Loading payroll run…</div>
      </div>
    );
  }

  if (!cycle) {
    return (
      <div style={{ padding: "40px 20px", textAlign: "center" }}>
        <div style={{ fontSize: 15, color: "var(--error)" }}>Payroll run not found.</div>
        <button className="btn btn-ghost" style={{ marginTop: 12 }} onClick={() => router.back()}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>
    );
  }

  const statusColor = STATUS_COLOR[cycle.status] ?? "var(--on-variant)";

  return (
    <div>
      {/* ── Back + Header ─────────────────────────────────────────────────── */}
      <button
        className="btn btn-ghost"
        style={{ marginBottom: 16, fontSize: 13 }}
        onClick={() => router.push("/dashboard/payroll")}
      >
        <i className="ti ti-arrow-left" /> Payroll
      </button>

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: "var(--on-bg)", margin: 0 }}>
              {period(cycle)}
            </h1>
            <span style={{ fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 20, background: `${statusColor}18`, color: statusColor, border: `1px solid ${statusColor}40` }}>
              {STATUS_LABEL[cycle.status] ?? cycle.status}
            </span>
          </div>
          <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 4 }}>
            {cycle.branch_name ?? "All Branches"} &nbsp;·&nbsp;
            {fmtDate(cycle.cycle_start)} – {fmtDate(cycle.cycle_end)} &nbsp;·&nbsp;
            Pay date: {fmtDate(cycle.pay_date)} &nbsp;·&nbsp;
            {cycle.payslip_count} employees
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {canDownloadEcr && (
            <>
              <button
                className="btn btn-primary"
                onClick={downloadEcr}
                disabled={downloading}
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                {downloading
                  ? <><i className="ti ti-loader-2 spin" /> Downloading…</>
                  : <><i className="ti ti-file-spreadsheet" /> Download ECR</>}
              </button>
              <button
                className="btn btn-ghost"
                onClick={downloadEcrText}
                disabled={downloadingText}
                title="EPFO Unified Portal ECR upload file (#~# delimited .txt)"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                {downloadingText
                  ? <><i className="ti ti-loader-2 spin" /> Downloading…</>
                  : <><i className="ti ti-file-text" /> Download ECR (Text)</>}
              </button>
              <button
                className="btn btn-ghost"
                onClick={downloadEsic}
                disabled={downloadingEsic}
                title="ESIC Challan — per-employee contribution report (internal, not the government upload file)"
                style={{ display: "flex", alignItems: "center", gap: 6 }}
              >
                {downloadingEsic
                  ? <><i className="ti ti-loader-2 spin" /> Downloading…</>
                  : <><i className="ti ti-file-spreadsheet" /> Download ESIC Challan</>}
              </button>
            </>
          )}
        </div>
      </div>

      {dlError && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-circle" /> {dlError}
        </div>
      )}

      {missingEsi && missingEsi.length > 0 && (
        <div className="alert alert-error" style={{ marginBottom: 16, display: "block" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
            <i className="ti ti-alert-circle" />
            {missingEsi.length} ESI-eligible employee{missingEsi.length === 1 ? "" : "s"} {missingEsi.length === 1 ? "has" : "have"} no ESI number on file — add it before filing:
          </div>
          <ul style={{ margin: 0, paddingLeft: 20, listStyle: "disc" }}>
            {missingEsi.map(m => (
              <li key={m.employee_code || m.employee_name} style={{ marginBottom: 2 }}>
                {m.employee_code ? (
                  <Link href={`/dashboard/employees/${m.employee_code}`} style={{ color: "inherit", textDecoration: "underline" }}>
                    {m.employee_name}
                  </Link>
                ) : (
                  m.employee_name
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {payslipsTruncated && (
        <div className="alert alert-warn" style={{ marginBottom: 16 }}>
          <i className="ti ti-alert-triangle" /> Showing {payslips.length} of {psData!.count} payslips. Summary totals below reflect only the visible rows. The ECR download still includes all employees.
        </div>
      )}

      {/* ── Summary Cards ─────────────────────────────────────────────────── */}
      {!loadPs && payslips.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 20 }}>
          {[
            { label: "Total Gross",      value: fmt(totalGross),      icon: "ti-cash" },
            { label: "Total Deductions", value: fmt(totalDeductions), icon: "ti-minus" },
            { label: "Net Payroll",      value: fmt(totalNet),        icon: "ti-transfer-in" },
            { label: "Total PF",         value: fmt(totalPF),         icon: "ti-building-community" },
          ].map(card => (
            <div key={card.label} className="card" style={{ padding: "14px 18px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                <i className={`ti ${card.icon}`} style={{ fontSize: 15, color: "var(--primary)" }} />
                <span style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".04em" }}>{card.label}</span>
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--on-bg)" }}>{card.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Payslips Table ────────────────────────────────────────────────── */}
      <div className="card" style={{ overflow: "hidden" }}>
        <div className="card-header">
          <div className="card-title"><i className="ti ti-receipt" /> Employee Payslips</div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{payslips.length} employees</span>
        </div>

        {loadPs ? (
          <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 14 }}>
            <i className="ti ti-loader-2 spin" /> Loading payslips…
          </div>
        ) : payslips.length === 0 ? (
          <div style={{ padding: "32px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 14 }}>
            No payslips generated for this cycle yet.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--bg-mid)" }}>
                  {["#", "Employee", "Dept", "Gross", "Deductions", "Net Pay", "PF", "LOP", "Status"].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 700, fontSize: 11, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".04em", whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {payslips.map((ps, idx) => (
                  <tr key={ps.id} style={{ borderTop: "1px solid var(--outline-v)" }}>
                    <td style={{ padding: "8px 12px", color: "var(--on-variant)", fontSize: 12 }}>{idx + 1}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <div style={{ fontWeight: 600, color: "var(--on-bg)" }}>{ps.employee_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{ps.employee_id_code}</div>
                    </td>
                    <td style={{ padding: "8px 12px", color: "var(--on-variant)" }}>{ps.department}</td>
                    <td style={{ padding: "8px 12px", fontWeight: 600, color: "var(--on-bg)" }}>{fmt(ps.gross_earnings)}</td>
                    <td style={{ padding: "8px 12px", color: "#dc2626" }}>{fmt(ps.total_deductions)}</td>
                    <td style={{ padding: "8px 12px", fontWeight: 700, color: "var(--primary)" }}>{fmt(ps.net_pay)}</td>
                    <td style={{ padding: "8px 12px", color: "var(--on-variant)" }}>{fmt(ps.pf_employee)}</td>
                    <td style={{ padding: "8px 12px", color: "var(--on-variant)", textAlign: "center" }}>{ps.lop_days}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{ fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 12, background: ps.status === "paid" ? "#dcfce7" : "#f3f4f6", color: ps.status === "paid" ? "#16a34a" : "var(--on-variant)" }}>
                        {ps.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
