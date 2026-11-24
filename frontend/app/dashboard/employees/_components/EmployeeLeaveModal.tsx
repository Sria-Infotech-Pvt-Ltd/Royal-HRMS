"use client";

// "Leave" from the employee drawer — the reference's Leave management dialog: the balances table (entitled /
// opening / accrued / availed / balance per type), a "Record leave" form for people allowed to record leave on
// someone's behalf (leave.record), and this leave year's history. Reads are scoped server-side: a Reporting
// Manager only gets their direct reports, branch-scoped roles only their own branch.

import { useT } from "@/hooks/useI18n";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { DURATION_OPTIONS, useRecordEmployeeLeave, type LeaveDuration } from "@/hooks/useRecordEmployeeLeave";
import { API } from "@/lib/api/endpoints";
import { financialYearRangeLabel, formatDateSlash } from "@/lib/formatDate";
import { currentFinancialYearStart } from "@/app/dashboard/my-payslip/_components/types";
import RefModal from "@/components/employees/RefModal";
import { fullName, type Employee } from "../_data";
import DateInput from "@/components/shared/DateInput";

interface BalanceRow {
  id: string;
  leave_type: string;
  leave_type_display: string;
  year: number;
  total_days: string;
  used_days: string;
  carried_forward: string;
  available_days: number;
  annual_entitlement: number;
}

interface LeaveHistoryRow {
  id: string;
  leave_type_display: string;
  total_days: string;
  start_date: string;
  end_date: string;
  reason: string;
  status: string;
  created_at: string;
}

// Order, short code and the one-line basis the reference shows under each type.
const LEAVE_TYPES: { type: string; code: string; basis: string }[] = [
  { type: "earned", code: "EL", basis: "Accrues 1.5 per completed month" },
  { type: "casual", code: "CL", basis: "Credited annually, lapses at year end" },
  { type: "sick", code: "SL", basis: "Credited annually, medical certificate beyond 3 days" },
  { type: "comp_off", code: "CO", basis: "Earned against approved holiday working, expires in 90 days" },
  { type: "maternity", code: "ML", basis: "26 weeks for the first two children — Maternity Benefit Act" },
  { type: "paternity", code: "PTL", basis: "Company policy, not statutory" },
  { type: "bereavement", code: "BL", basis: "Granted on request" },
  { type: "lwp", code: "LOP", basis: "Unpaid — deducted in the payroll run" },
];
const EVENT_TYPES = new Set(["comp_off", "maternity", "paternity", "bereavement", "lwp"]);

const num = (value: string | number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Number(parsed.toFixed(1)).toString() : "0";
};

export default function EmployeeLeaveModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const t = useT();
  const canRecord = usePermission("leave.record");
  const balances = useFetch<BalanceRow[]>(`${API.leave.balance}?employee_id=${encodeURIComponent(employee.code)}`);
  const history = useFetch<{ results: LeaveHistoryRow[] }>(
    `${API.leave.requests}?employee_id=${encodeURIComponent(employee.code)}&status=approved&page_size=50`,
  );
  const fyConfig = useFetch<{ financial_year_start_month: string }>(API.settings.financialYear);

  const byType = new Map((balances.data ?? []).map(row => [row.leave_type, row]));
  const rows = LEAVE_TYPES.filter(entry => byType.has(entry.type)).map(entry => ({ ...entry, row: byType.get(entry.type) as BalanceRow }));
  const lopDays = Number(byType.get("lwp")?.used_days ?? 0);
  const yearLabel = fyConfig.data ? financialYearRangeLabel(currentFinancialYearStart(fyConfig.data.financial_year_start_month)) : "";
  const thisYear = balances.data?.[0]?.year;
  const recorded = (history.data?.results ?? []).filter(item => !thisYear || new Date(item.start_date).getFullYear() === thisYear);

  const form = useRecordEmployeeLeave(employee.code, rows[0]?.type ?? "casual", () => { balances.refetch(); history.refetch(); });

  return (
    <RefModal
      title={t("Leave")} accent={t("management")}
      subtitle={`${fullName(employee)} · ${employee.code} — ${employee.designation || "—"}`}
      onClose={onClose}
      note={<span style={lopDays > 0 ? { color: "var(--crit)" } : undefined}>
        {lopDays > 0
          ? (lopDays === 1 ? t("{count} day loss of pay — deducted in the next payroll run.", { count: num(lopDays) }) : t("{count} days loss of pay — deducted in the next payroll run.", { count: num(lopDays) }))
          : t("No loss of pay this leave year.")}
      </span>}
      actions={<button className="rvbtn" type="button" onClick={onClose}>{t("Close")}</button>}
    >
      <div className="sechead">{t("BALANCES")} <span className="own hr">{t("HR")}</span></div>
      <div className="hint">{t("Standard India Leave Policy · leave year {year} · balances in days", { year: yearLabel || thisYear || "—" })}</div>
      {balances.error && <div className="alert alert-error">{balances.error}</div>}
      <div className="lv-h">
        <div>{t("LEAVE TYPE")}</div><div className="lv-num">{t("ENTITLED")}</div><div className="lv-num">{t("OPENING")}</div>
        <div className="lv-num">{t("ACCRUED")}</div><div className="lv-num">{t("AVAILED")}</div><div className="lv-bal">{t("BALANCE")}</div>
      </div>
      {balances.loading ? (
        <div className="hint">{t("Loading balances…")}</div>
      ) : rows.length === 0 ? (
        <div className="hint">{t("No leave balances have been credited for this employee yet.")}</div>
      ) : (
        rows.map(({ type, code, basis, row }) => {
          const isEvent = EVENT_TYPES.has(type);
          const balance = type === "lwp" ? 0 : row.available_days;
          const tone = balance <= 0 ? " zero" : balance < 3 && !isEvent ? " low" : "";
          return (
            <div className="lv-r" key={type}>
              <div><div className="nm">{row.leave_type_display} <span className="tag">{code}</span></div><div className="sub">{t(basis)}</div></div>
              <div className="lv-num">{row.annual_entitlement ? num(row.annual_entitlement) : "—"}</div>
              <div className="lv-num">{num(row.carried_forward)}</div>
              <div className="lv-num">{isEvent ? "—" : num(Number(row.total_days) - Number(row.carried_forward))}</div>
              <div className="lv-num">{num(row.used_days)}</div>
              <div className={`lv-bal${tone}`}>{num(balance)}</div>
            </div>
          );
        })
      )}

      {canRecord && (
        <>
          <div className="divider" />
          <div className="sechead">{t("RECORD LEAVE")} <span className="own emp">{t("HR / EMPLOYEE")}</span></div>
          {form.error && <div className="alert alert-error">{form.error}</div>}
          <div className="g3">
            <div className="f">
              <label>{t("Leave type")}</label>
              <select className="finput" value={form.type} onChange={event => form.setLeaveType(event.target.value)}>
                {rows.map(entry => <option key={entry.type} value={entry.type}>{entry.row.leave_type_display}</option>)}
              </select>
            </div>
            <div className="f"><label>{t("From")}</label><DateInput className="finput" value={form.from} onChange={isoDate => form.setFrom(isoDate)} /></div>
            <div className="f"><label>{t("To")}</label><DateInput className="finput" value={form.to} onChange={isoDate => form.setTo(isoDate)} /></div>
            <div className="f">
              <label>{t("Duration")}</label>
              <select className="finput" value={form.duration} onChange={event => form.setDuration(event.target.value as LeaveDuration)}>
                {DURATION_OPTIONS.map(option => <option key={option.value} value={option.value}>{t(option.label)}</option>)}
              </select>
              <div className="hint">{t("Half day applies to single-day requests only.")}</div>
            </div>
            <div className="f" style={{ gridColumn: "span 2" }}>
              <label>{t("Reason")}</label>
              <input className="finput" value={form.reason} placeholder={t("Optional")} onChange={event => form.setReason(event.target.value)} />
            </div>
          </div>
          <div className="hint">
            {form.days
              ? (form.days === 1 ? t("{count} day — weekly offs (Saturday and Sunday) excluded.", { count: form.days }) : t("{count} days — weekly offs (Saturday and Sunday) excluded.", { count: form.days }))
              : t("Weekly offs (Saturday and Sunday) are excluded from the day count.")}
          </div>
          <div><button className="rvbtn pri" type="button" onClick={form.record} disabled={form.saving}>{form.saving ? t("Recording…") : t("Record leave")}</button></div>
        </>
      )}

      <div className="divider" />
      <div className="sechead">{t("LEAVE HISTORY")}</div>
      {recorded.length === 0 ? (
        <div className="hint">{t("No leave recorded in this leave year.")}</div>
      ) : (
        recorded.map(item => (
          <div className="actrow live" key={item.id}>
            <span className="bar" />
            <div className="meta">
              <div className="t1">{item.leave_type_display} <span className="chip ok">{Number(item.total_days) === 1 ? t("{count} day", { count: num(item.total_days) }) : t("{count} days", { count: num(item.total_days) })}</span></div>
              <div className="t2">{item.reason || t("No reason recorded")} · {t("recorded {date}", { date: formatDateSlash(item.created_at) })}</div>
            </div>
            <div className="dates" style={{ textAlign: "right" }}>
              {formatDateSlash(item.start_date)}
              <div className="actdel">{t("to {date}", { date: formatDateSlash(item.end_date) })}</div>
            </div>
          </div>
        ))
      )}
    </RefModal>
  );
}
