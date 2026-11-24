"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import ConfirmModal from "@/components/ConfirmModal";
import type { EmployeePayslip, PayrollCycle } from "@/types/payroll";
import { formatDate } from "@/lib/formatDate";

interface Props {
  cycleId: string;
  onNext: () => void;
  onBack: () => void;
}

interface PagedResponse<T> { results: T[]; count: number; }

interface SalaryTransferStatus {
  employee_side_ready: boolean;
  reason: string;
  batch_status: "confirmed" | "cancelled" | null;
  item_count: number;
}

const fmt = (n: number | string) =>
  `₹${Number(n).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;

export default function BankTransferStep({ cycleId, onNext, onBack }: Props) {
  const t = useT();
  const { data: payslipPage, loading, refetch } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));
  const { data: cycle, refetch: refetchCycle } = useFetch<PayrollCycle>(API.payroll.cycle(cycleId));
  const { data: transferStatus, loading: transferLoading, refetch: refetchTransfer } =
    useFetch<SalaryTransferStatus>(API.payroll.salaryTransferStatus(cycleId));

  const [marking, setMarking] = useState(false);
  const [confirmingTransfer, setConfirmingTransfer] = useState(false);
  const [downloadingTransfer, setDownloadingTransfer] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [showTransferConfirm, setShowTransferConfirm] = useState(false);

  const payslips = payslipPage?.results ?? [];
  const totalNet = payslips.reduce((s, p) => s + Number(p.net_pay), 0);
  const isPaid   = cycle?.status === "paid" || cycle?.status === "closed";
  const transferConfirmed = transferStatus?.batch_status === "confirmed";

  async function confirmTransfer() {
    setShowTransferConfirm(false);
    setConfirmingTransfer(true);
    setErr(null);
    try {
      await clientApi.post(API.payroll.salaryTransferConfirm(cycleId));
      refetchTransfer();
    } catch (error: unknown) {
      setErr((error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? t("Failed to confirm the salary transfer."));
    } finally {
      setConfirmingTransfer(false);
    }
  }

  async function downloadTransferFile() {
    setDownloadingTransfer(true);
    setErr(null);
    try {
      const response = await clientApi.get(API.payroll.salaryTransferDownload(cycleId), { responseType: "blob" });
      const url = URL.createObjectURL(response.data as Blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `salary-transfer-${cycle?.cycle_start ?? cycleId}.csv`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      refetchTransfer();
    } catch (error: unknown) {
      setErr((error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? t("Failed to download the bank transfer file."));
    } finally {
      setDownloadingTransfer(false);
    }
  }

  async function markPaid() {
    setShowConfirm(false);
    setMarking(true);
    setErr(null);
    try {
      await clientApi.post(API.payroll.markPaid(cycleId));
      refetch();
      refetchCycle();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message
        ?? t("Failed to mark as paid.");
      setErr(msg);
    } finally {
      setMarking(false);
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-circle-check" /> {t("Mark Payroll as Paid")}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span className="badge badge-primary">{t("{amount} total", { amount: fmt(totalNet) })}</span>
          {isPaid && <span className="badge badge-success"><i className="ti ti-check" /> {t("Paid")}</span>}
        </div>
      </div>

      {isPaid && (
        <div className="alert alert-success" style={{ margin: "0", borderRadius: 0 }}>
          <i className="ti ti-circle-check" />
          <span>{t("All salaries marked as paid. Payroll run for this cycle is complete.")}</span>
        </div>
      )}

      {err && (
        <div className="alert alert-error" style={{ margin: "0", borderRadius: 0 }}>
          <i className="ti ti-alert-circle" />
          <span>{err}</span>
        </div>
      )}

      {!isPaid && (
        <div className={`alert ${transferConfirmed ? "alert-success" : "alert-info"}`} style={{ margin: 0, borderRadius: 0 }}>
          <i className={`ti ${transferConfirmed ? "ti-lock-check" : "ti-building-bank"}`} />
          <span>
            {transferLoading
              ? t("Checking salary transfer readiness…")
              : transferConfirmed
                ? t("Salary transfer locked for {count} employee(s). Download the NEFT CSV and submit it to your bank before marking payroll paid.", { count: transferStatus?.item_count ?? 0 })
                : transferStatus?.employee_side_ready
                  ? t("Employees have acknowledged their payslips. Confirm the salary transfer to lock bank details and generate the NEFT CSV.")
                  : transferStatus?.reason || t("Salary transfer readiness is unavailable.")}
          </span>
        </div>
      )}

      {/* Summary */}
      <div style={{ padding: "20px", display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, borderBottom: "1px solid var(--outline-v)" }}>
        <div className="stat-card">
          <div className="stat-label">{t("Employees")}</div>
          <div className="stat-value">{payslips.length}</div>
          <div className="stat-sub">{t("In this payroll run")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t("Total Net Payable")}</div>
          <div className="stat-value" style={{ color: "var(--success)" }}>{fmt(totalNet)}</div>
          <div className="stat-sub">{t("Gross − all deductions")}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">{t("Status")}</div>
          <div className="stat-value" style={{ color: isPaid ? "var(--success)" : "var(--warn)", fontSize: 18 }}>
            {isPaid ? t("Paid") : t("Pending")}
          </div>
          <div className="stat-sub">{cycle?.pay_date ? t("Pay date: {date}", { date: formatDate(cycle.pay_date) }) : "—"}</div>
        </div>
      </div>

      {/* Payslip list */}
      {loading ? (
        <div style={{ padding: "32px", textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 24 }} />
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("Employee")}</th>
                <th>{t("Org Unit")}</th>
                <th>{t("Company Code")}</th>
                <th style={{ textAlign: "right", color: "var(--success)" }}>{t("Net Salary")}</th>
                <th>{t("Status")}</th>
              </tr>
            </thead>
            <tbody>
              {payslips.map(p => (
                <tr key={p.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                        {p.employee_name.charAt(0)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13 }}>{p.employee_name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.employee_id_code}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ fontSize: 13 }}>{p.department || "—"}</td>
                  <td style={{ fontSize: 13 }}>{p.branch || "—"}</td>
                  <td style={{ textAlign: "right", fontWeight: 700, color: "var(--success)", fontSize: 14 }}>{fmt(p.net_pay)}</td>
                  <td>
                    <span className={`badge ${p.status === "paid" ? "badge-success" : "badge-info"}`}>
                      {p.status.charAt(0).toUpperCase() + p.status.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
              {payslips.length > 0 && (
                <tr style={{ background: "var(--bg-low)" }}>
                  <td style={{ fontWeight: 700 }} colSpan={3}>{t("Total Net Payable")}</td>
                  <td style={{ textAlign: "right", fontWeight: 800, color: "var(--success)", fontSize: 15 }}>{fmt(totalNet)}</td>
                  <td />
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8 }}>
          {!isPaid && !transferConfirmed && (
            <button
              className="btn btn-outline"
              onClick={() => setShowTransferConfirm(true)}
              disabled={confirmingTransfer || transferLoading || !transferStatus?.employee_side_ready}
            >
              {confirmingTransfer
                ? <><i className="ti ti-loader-2 animate-spin" /> {t("Locking Transfer…")}</>
                : <><i className="ti ti-lock" /> {t("Confirm Salary Transfer")}</>}
            </button>
          )}
          {!isPaid && transferConfirmed && (
            <button
              className="btn btn-outline"
              onClick={downloadTransferFile}
              disabled={downloadingTransfer}
            >
              {downloadingTransfer
                ? <><i className="ti ti-loader-2 animate-spin" /> {t("Preparing CSV…")}</>
                : <><i className="ti ti-download" /> {t("Download NEFT CSV")}</>}
            </button>
          )}
          {!isPaid && (
            <button
              className="btn btn-success"
              onClick={() => setShowConfirm(true)}
              disabled={marking || payslips.length === 0 || !transferConfirmed}
            >
              {marking
                ? <><i className="ti ti-loader-2 animate-spin" /> {t("Marking Paid…")}</>
                : <><i className="ti ti-checks" /> {t("Mark All Paid")}</>}
            </button>
          )}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack} disabled={isPaid}>
            <i className="ti ti-arrow-left" /> {t("Back")}
          </button>
          <button
            className="btn btn-filled"
            onClick={onNext}
            disabled={!isPaid}
            style={{ opacity: isPaid ? 1 : 0.5 }}
          >
            <i className="ti ti-circle-check" /> {t("Finish Payroll Run")}
          </button>
        </div>
      </div>

      {showConfirm && (
        <ConfirmModal
          title={t("Mark payroll as paid?")}
          body={payslips.length === 1
            ? t("This marks all {count} payslip (total {amount}) as paid and closes this payroll run. This does not itself transfer money — it records that the transfer already happened. This cannot be undone.", { count: payslips.length, amount: fmt(totalNet) })
            : t("This marks all {count} payslips (total {amount}) as paid and closes this payroll run. This does not itself transfer money — it records that the transfer already happened. This cannot be undone.", { count: payslips.length, amount: fmt(totalNet) })}
          confirmLabel={t("Mark All Paid")}
          saving={marking}
          onConfirm={markPaid}
          onCancel={() => setShowConfirm(false)}
        />
      )}

      {showTransferConfirm && (
        <ConfirmModal
          title={t("Confirm salary transfer?")}
          body={t("This locks the current bank details and net pay for all {count} employee(s) into a transfer batch. Download the NEFT CSV after confirmation and submit it through your bank before marking payroll paid.", { count: payslips.length })}
          confirmLabel={t("Confirm and Lock")}
          saving={confirmingTransfer}
          onConfirm={confirmTransfer}
          onCancel={() => setShowTransferConfirm(false)}
        />
      )}
    </div>
  );
}
