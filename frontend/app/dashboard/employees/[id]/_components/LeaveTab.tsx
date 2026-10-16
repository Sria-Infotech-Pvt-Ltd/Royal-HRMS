"use client";

import { useState, useMemo } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useEmployeeLeave } from "@/hooks/useEmployeeLeave";
import {
  STATUS_BADGE, STATUS_LABEL, fmtShortDate,
  buildLeaveTypesList, CUSTOM_LEAVE_TYPE_DEFAULTS,
  type LeaveRequest, type LeavePolicy, type BalanceSummary,
} from "@/app/dashboard/leave/_data";
import LeaveRequestDetailModal from "@/app/dashboard/leave/_components/LeaveRequestDetailModal";
import LopBadge from "@/app/dashboard/leave/_components/LopBadge";
import LeaveCreditsSection from "./LeaveCreditsSection";
import MonthlyLeaveStatement, { MonthlyCreditsTable } from "@/components/leave/MonthlyLeaveStatement";
import { defaultMonth, monthOf, splitBySchedule, type ScheduleView } from "@/lib/leaveStatement";

interface Props {
  employeeId: string;
}

// Bespoke icon/color this tab has always used for these 3 types specifically
// — kept exactly as before. Any other type (maternity, paternity, or any
// custom Leave Type such as "Pink Leave") is resolved dynamically below via
// buildLeaveTypesList(), the same resolver ApplyLeaveForm already uses, so
// there's one shared place that knows about custom Leave Types, not two.
const CURATED_STYLE: Record<string, { icon: string; iconClass: string; barColor: string }> = {
  casual: { icon: "ti-circle-check", iconClass: "si-success", barColor: "var(--success)" },
  earned: { icon: "ti-calendar",     iconClass: "si-primary", barColor: "var(--primary)" },
  sick:   { icon: "ti-stethoscope",  iconClass: "si-info",    barColor: "var(--info)"    },
};

// Loss of Pay already has its own dedicated card below, driven by
// stats.lop_days/lop_requests (days used as LOP across requests) — a
// different concept from an allocated/available balance. Its LeaveBalance
// row (if one exists) must never also render as a normal balance card here.
const LWP_KEY = "lwp";

export function LeaveTab({ employeeId }: Props) {
  const [detailRequest, setDetailRequest] = useState<LeaveRequest | null>(null);
  // View and month live here, so switching views (or years) keeps both.
  const [view, setView] = useState<ScheduleView>("annual");
  const [month, setMonth] = useState<number | null>(null);
  const { year, prevYear, nextYear, page, setPage, totalPages, requests, stats, loading, error, refetch } =
    useEmployeeLeave(employeeId);

  // Same policy data + resolver ApplyLeaveForm uses, so a custom Leave
  // Type's display name/icon/color is never hardcoded here either.
  const { data: policies } = useFetch<LeavePolicy[]>(API.leave.policy);
  const leaveTypes = useMemo(() => buildLeaveTypesList(policies), [policies]);
  const leaveTypeMap = useMemo(
    () => Object.fromEntries(leaveTypes.map(lt => [lt.key, lt])),
    [leaveTypes],
  );

  const balances = (stats?.balances ?? []).filter(b => b.leave_type !== LWP_KEY);
  // Each leave type goes to the view matching its policy's credit_schedule (from the
  // backend). A type whose schedule is unknown (no policy) is listed separately, never guessed.
  const groups = splitBySchedule(balances);
  const visible = view === "monthly" ? groups.monthly : groups.annual;
  const selectedMonth = month ?? defaultMonth(year);
  const monthOptions = Array.from({ length: 12 }, (_, i) => ({
    value: i + 1, label: new Date(year, i, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" }),
  }));
  const labelOf = (b: BalanceSummary) => leaveTypeMap[b.leave_type]?.label ?? b.leave_type_display;

  if (error) {
    return (
      <div className="alert alert-error">
        <i className="ti ti-alert-circle" /> {error}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Annual / Monthly view selector */}
      <div role="tablist" aria-label="Leave credit schedule" style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {(["annual", "monthly"] as const).map(v => (
          <button
            key={v}
            type="button"
            role="tab"
            aria-selected={view === v}
            className={`btn btn-sm ${view === v ? "btn-filled" : "btn-ghost"}`}
            onClick={() => setView(v)}
          >
            <i className={`ti ${v === "annual" ? "ti-calendar" : "ti-calendar-stats"}`} />
            {v === "annual" ? `Annual leave (${groups.annual.length})` : `Monthly leave (${groups.monthly.length})`}
          </button>
        ))}
        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
          Grouped by each leave type&apos;s credit schedule in Leave Policy.
        </span>
      </div>

      {groups.unclassified.length > 0 && (
        <div className="alert alert-warn">
          <i className="ti ti-alert-triangle" />
          <div>
            No leave policy found for: {groups.unclassified.map(b => `${labelOf(b)} (${b.available} available)`).join(", ")}.
            These aren&apos;t shown as annual or monthly — check Settings → Leave Management → Leave Types.
          </div>
        </div>
      )}

      <div className="stats-grid" style={{ marginBottom: 0 }}>
        {!loading && visible.length === 0 && (
          <div className="stat-card" style={{ gridColumn: "1 / -1" }}>
            <div className="stat-label">{view === "monthly" ? "No monthly leave types" : "No annual leave types"}</div>
            <div className="stat-sub">
              {view === "monthly"
                ? "No leave type for this employee is set to the Monthly credit schedule. Set one in Settings → Leave Management → Leave Policy → Monthly Credit Settings."
                : "Every leave type for this employee is on the Monthly credit schedule — see the Monthly leave view."}
            </div>
          </div>
        )}
        {visible.map(b => {
          const curated  = CURATED_STYLE[b.leave_type];
          const lt       = leaveTypeMap[b.leave_type];
          const label    = labelOf(b);
          const icon     = curated?.icon ?? lt?.icon ?? CUSTOM_LEAVE_TYPE_DEFAULTS.icon;
          const barColor = curated?.barColor ?? lt?.color ?? CUSTOM_LEAVE_TYPE_DEFAULTS.color;
          const iconBg   = lt?.bg ?? CUSTOM_LEAVE_TYPE_DEFAULTS.bg;
          const total    = Number(b.total_days);
          const left     = Number(b.available);
          const used     = Number(b.used_days);
          const pct      = total > 0 ? Math.round((used / total) * 100) : 0;
          const isMonthly = view === "monthly";
          const thisMonth = isMonthly ? monthOf(b.statement, selectedMonth) : null;
          return (
            <div key={b.leave_type} className="stat-card">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
                <div>
                  <div className="stat-label">{label}</div>
                  <div className="stat-value">{loading ? "—" : left}</div>
                  {isMonthly ? (
                    // Not "of N days": a monthly type's yearly total is the credits recorded so far,
                    // not an allocation.
                    <div className="stat-sub">
                      available now
                      {thisMonth ? ` · ${thisMonth.credit} credited in ${thisMonth.label}` : ""}
                      {b.statement?.total_credited != null ? ` · ${b.statement.total_credited} in ${year}` : ""}
                    </div>
                  ) : (
                    <div className="stat-sub">of {total} days left</div>
                  )}
                </div>
                {curated ? (
                  <div className={`stat-icon ${curated.iconClass}`} style={{ float: "none", margin: 0 }}>
                    <i className={`ti ${curated.icon}`} />
                  </div>
                ) : (
                  <div className="stat-icon" style={{ float: "none", margin: 0, background: iconBg, color: barColor }}>
                    <i className={`ti ${icon}`} />
                  </div>
                )}
              </div>
              {!isMonthly && (
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${pct}%`, background: barColor }} />
                </div>
              )}
            </div>
          );
        })}

        {/* Operational summaries — not leave policies, shown in both views */}
        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Pending Requests</div>
              <div className="stat-value">{loading ? "—" : stats?.pending ?? 0}</div>
              <div className="stat-sub">Awaiting approval</div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-clock" />
            </div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
        </div>

        <div className="stat-card">
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 10 }}>
            <div>
              <div className="stat-label">Loss of Pay (LOP)</div>
              <div className="stat-value" style={{ color: "var(--warn)" }}>{loading ? "—" : stats?.lop_days ?? 0}</div>
              <div className="stat-sub">
                {loading ? "" : `${stats?.lop_requests ?? 0} request${(stats?.lop_requests ?? 0) !== 1 ? "s" : ""} in ${year}`}
              </div>
            </div>
            <div className="stat-icon si-warn" style={{ float: "none", margin: 0 }}>
              <i className="ti ti-coin-off" />
            </div>
          </div>
          <div className="progress-bar"><div className="progress-fill" style={{ width: 0 }} /></div>
        </div>
      </div>

      {view === "annual" ? (
        <LeaveCreditsSection employeeId={employeeId} onChanged={refetch} schedule="annual" />
      ) : groups.monthly.length > 0 && (
        <>
          <MonthlyCreditsTable
            rows={groups.monthly.map(b => ({
              leave_type: b.leave_type, label: labelOf(b),
              month: monthOf(b.statement, selectedMonth), hasStatement: !!b.statement,
            }))}
            year={year}
            month={selectedMonth}
            monthOptions={monthOptions}
            onMonth={setMonth}
          />
          {groups.monthly.filter(b => b.statement).map((b, i) => (
            <MonthlyLeaveStatement
              key={`${b.leave_type}-${year}`}
              label={labelOf(b)}
              year={year}
              stmt={b.statement!}
              total={Number(b.total_days)}
              used={Number(b.used_days)}
              available={Number(b.available)}
              defaultOpen={i === 0}
            />
          ))}
        </>
      )}

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-list-details" /> Leave Requests
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <button className="btn btn-ghost btn-sm" onClick={prevYear} disabled={loading}>
              <i className="ti ti-chevron-left" />
            </button>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", minWidth: 48, textAlign: "center" }}>
              {year}
            </span>
            <button className="btn btn-ghost btn-sm" onClick={nextYear} disabled={loading}>
              <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
        <div className="table-wrap">
          {loading ? (
            <div style={{ padding: "40px 20px", textAlign: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 24, color: "var(--outline-v)" }} />
            </div>
          ) : requests.length === 0 ? (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
              No leave requests found for {year}.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Leave Type</th>
                  <th>From</th>
                  <th>To</th>
                  <th style={{ textAlign: "center" }}>Days</th>
                  <th>Applied On</th>
                  <th>Approver</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {requests.map(r => (
                  <tr key={r.id} onClick={() => setDetailRequest(r)} style={{ cursor: "pointer" }}>
                    <td>{r.leave_type_display}</td>
                    <td>{fmtShortDate(r.start_date)}</td>
                    <td>{fmtShortDate(r.end_date)}</td>
                    <td style={{ textAlign: "center", fontWeight: 700 }}>
                      {r.total_days}
                      <LopBadge request={r} />
                    </td>
                    <td style={{ fontSize: 12, color: "var(--on-variant)" }}>{fmtShortDate(r.created_at?.slice(0, 10))}</td>
                    <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                      {r.approved_by || "—"}
                      {r.approved_at
                        ? <div style={{ fontSize: 11, color: "var(--outline)" }}>{fmtShortDate(r.approved_at.slice(0, 10))}</div>
                        : <div style={{ fontSize: 11, color: "var(--outline)" }}>Not yet actioned</div>}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {totalPages > 1 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
              <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {page} of {totalPages}</span>
              <div style={{ display: "flex", gap: 6 }}>
                <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                  <i className="ti ti-chevron-left" /> Prev
                </button>
                <button className="btn btn-ghost btn-sm" disabled={page >= totalPages} onClick={() => setPage(p => Math.min(p + 1, totalPages))}>
                  Next <i className="ti ti-chevron-right" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {detailRequest && (
        <LeaveRequestDetailModal
          requestId={detailRequest.id}
          initialData={detailRequest}
          onClose={() => setDetailRequest(null)}
        />
      )}
    </div>
  );
}
