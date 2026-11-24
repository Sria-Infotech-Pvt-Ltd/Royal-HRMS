"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import { API } from "@/lib/api/endpoints";
import type { EmployeePayslip } from "@/types/payroll";

interface Props { cycleId: string; onNext: () => void; onBack: () => void; }
interface PagedResponse<T> { results: T[]; count: number; }

type IssueSeverity = "error" | "warn" | "info";
type IssueStatus   = "open" | "reviewed" | "ignored";

interface Issue {
  id:        string;
  type:      string;
  employees: string[];
  severity:  IssueSeverity;
  message:   string;
  status:    IssueStatus;
}

const SEV_CONFIG: Record<IssueSeverity, { icon: string; badge: string; label: string; borderColor: string; iconColor: string }> = {
  error: { icon: "ti-alert-circle",   badge: "badge badge-error", label: "Error",   borderColor: "#ffb3ae", iconColor: "var(--error)" },
  warn:  { icon: "ti-alert-triangle", badge: "badge badge-warn",  label: "Warning", borderColor: "#fde68a", iconColor: "var(--warn)"  },
  info:  { icon: "ti-info-circle",    badge: "badge badge-info",  label: "Info",    borderColor: "#b3d1f5", iconColor: "var(--info)"  },
};

function deriveIssues(payslips: EmployeePayslip[]): Issue[] {
  const issues: Issue[] = [];

  if (payslips.length === 0) {
    issues.push({
      id: "no-payslips", type: tr("No Payslips Generated"), employees: [], severity: "error", status: "open",
      message: tr("No payslips were generated. Click Back → Back → Earn & Deduct → \"Compute Salaries\" to reprocess after ensuring all employees have CTC configured."),
    });
    return issues;
  }

  const zeroGross = payslips.filter(p => Number(p.gross_earnings) === 0);
  if (zeroGross.length > 0) {
    issues.push({
      id: "zero-gross", type: tr("Zero Gross Earnings"), employees: zeroGross.map(p => p.employee_name), severity: "error", status: "open",
      message: tr("{count} employee(s) have zero gross earnings. Check that their CTC and salary structure are configured correctly.", { count: zeroGross.length }),
    });
  }

  const negativeNet = payslips.filter(p => Number(p.net_pay) < 0);
  if (negativeNet.length > 0) {
    issues.push({
      id: "negative-net", type: tr("Negative Net Pay"), employees: negativeNet.map(p => p.employee_name), severity: "error", status: "open",
      message: tr("{count} employee(s) have negative net pay. Deductions exceed gross earnings — review LOP or advance recovery entries.", { count: negativeNet.length }),
    });
  }

  const highLop = payslips.filter(p => Number(p.lop_days) > 15);
  if (highLop.length > 0) {
    issues.push({
      id: "high-lop", type: tr("High Loss of Pay (>15 days)"), employees: highLop.map(p => p.employee_name), severity: "warn", status: "open",
      message: tr("{count} employee(s) have more than 15 LOP days. Verify this is correct before proceeding.", { count: highLop.length }),
    });
  }

  const noDeductions = payslips.filter(p => Number(p.total_deductions) === 0 && Number(p.gross_earnings) > 21000);
  if (noDeductions.length > 0) {
    issues.push({
      id: "no-deductions", type: tr("No Statutory Deductions Applied"), employees: noDeductions.map(p => p.employee_name), severity: "warn", status: "open",
      message: tr("{count} employee(s) earning above ₹21,000 have no deductions. Ensure statutory config is set for their branch.", { count: noDeductions.length }),
    });
  }

  return issues;
}

export default function ValidationStep({ cycleId, onNext, onBack }: Props) {
  const t = useT();
  const [statuses, setStatuses] = useState<Record<string, IssueStatus>>({});

  const { data: payslipPage, loading } =
    useFetch<PagedResponse<EmployeePayslip>>(API.payroll.cyclePayslips(cycleId));

  const payslips = useMemo(() => payslipPage?.results ?? [], [payslipPage]);

  const baseIssues = useMemo(() => deriveIssues(payslips), [payslips]);
  const issues = baseIssues.map(i => ({ ...i, status: statuses[i.id] ?? i.status }));

  function markReviewed(id: string) { setStatuses(p => ({ ...p, [id]: "reviewed" })); }
  function ignore(id: string)       { setStatuses(p => ({ ...p, [id]: "ignored" }));  }

  const hasNoPayslips = issues.some(i => i.id === "no-payslips");
  const openErrors   = issues.filter(i => i.severity === "error" && i.status === "open").length;
  const openWarnings = issues.filter(i => i.severity === "warn"  && i.status === "open").length;
  const openCount    = issues.filter(i => i.status === "open").length;
  const canContinue  = !loading && openErrors === 0 && !hasNoPayslips;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-shield-check" /> {t("Validation")}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {loading && <span className="badge badge-neutral"><i className="ti ti-loader-2 animate-spin" /> {t("Checking…")}</span>}
          {!loading && openErrors > 0   && <span className="badge badge-error"><i className="ti ti-alert-circle" /> {openErrors === 1 ? t("{count} Error", { count: openErrors }) : t("{count} Errors", { count: openErrors })}</span>}
          {!loading && openWarnings > 0 && <span className="badge badge-warn"><i className="ti ti-alert-triangle" /> {openWarnings === 1 ? t("{count} Warning", { count: openWarnings }) : t("{count} Warnings", { count: openWarnings })}</span>}
          {!loading && openCount === 0  && <span className="badge badge-success"><i className="ti ti-check" /> {t("All Clear")}</span>}
        </div>
      </div>

      <div className="card-body">
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 32, display: "block", marginBottom: 12 }} />
            {t("Running validation checks…")}
          </div>
        ) : (
          <>
            {openErrors > 0 && (
              <div className="alert alert-error" style={{ marginBottom: 20 }}>
                <i className="ti ti-alert-circle" />
                <span><strong>{t("{count} critical error(s)", { count: openErrors })}</strong> {t("must be resolved or explicitly ignored before proceeding.")}</span>
              </div>
            )}
            {canContinue && openCount > 0 && (
              <div className="alert alert-warn" style={{ marginBottom: 20 }}>
                <i className="ti ti-alert-triangle" />
                <span>{t("No critical errors. You may continue with {count} unresolved warning(s).", { count: openCount })}</span>
              </div>
            )}
            {openCount === 0 && issues.length > 0 && (
              <div className="alert alert-success" style={{ marginBottom: 20 }}>
                <i className="ti ti-circle-check" />
                <span>{t("All validation checks passed or acknowledged. Ready to generate payslips.")}</span>
              </div>
            )}
            {issues.length === 0 && (
              <div className="alert alert-success" style={{ marginBottom: 20 }}>
                <i className="ti ti-circle-check" />
                <span>{t("No issues detected. All {count} payslips look correct.", { count: payslips.length })}</span>
              </div>
            )}

            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {issues.map(issue => {
                const cfg   = SEV_CONFIG[issue.severity];
                const isDone = issue.status !== "open";
                return (
                  <div
                    key={issue.id}
                    style={{
                      border: `1.5px solid ${isDone ? "var(--outline-v)" : cfg.borderColor}`,
                      borderRadius: "var(--radius)", padding: "14px 16px",
                      background: isDone ? "var(--bg-low)" : "transparent",
                      opacity: isDone ? 0.65 : 1,
                      display: "flex", alignItems: "flex-start", gap: 14,
                    }}
                  >
                    <i className={`ti ${cfg.icon}`} style={{ fontSize: 20, color: isDone ? "var(--outline)" : cfg.iconColor, marginTop: 1, flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{issue.type}</span>
                        <span className={cfg.badge}>{t(cfg.label)}</span>
                        {isDone && (
                          <span className={`badge ${issue.status === "reviewed" ? "badge-success" : "badge-neutral"}`}>
                            {issue.status === "reviewed" ? t("Reviewed") : t("Ignored")}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 8 }}>{issue.message}</div>
                      {issue.employees.length > 0 && (
                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                          {issue.employees.map((name, i) => (
                            <span key={`${i}-${name}`} className="badge badge-neutral">{name}</span>
                          ))}
                        </div>
                      )}
                    </div>
                    {!isDone && issue.id !== "no-payslips" && (
                      <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                        <button className="btn btn-success btn-sm" onClick={() => markReviewed(issue.id)}>
                          <i className="ti ti-check" /> {t("Reviewed")}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => ignore(issue.id)}>
                          <i className="ti ti-eye-off" /> {t("Ignore")}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> {t("Back")}</button>
        <button className="btn btn-filled" onClick={onNext} disabled={!canContinue}>
          {t("Continue")} <i className="ti ti-arrow-right" />
        </button>
      </div>
    </div>
  );
}
