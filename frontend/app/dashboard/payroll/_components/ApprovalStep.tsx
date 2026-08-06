"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PayrollCycle, PayrollSettings, ManagerApprovalStatus } from "@/types/payroll";

interface Props {
  cycleId: string;
  settings: PayrollSettings | null;
  onNext: () => void;
  onBack: () => void;
}

function fmt(dateStr: string | null | undefined) {
  if (!dateStr) return null;
  return new Date(dateStr).toLocaleString("en-IN", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function ApprovalStep({ cycleId, settings, onNext, onBack }: Props) {
  const { data: cycle, loading: cycleLoading, refetch: refetchCycle } =
    useFetch<PayrollCycle>(API.payroll.cycle(cycleId));

  const { data: mgrs, loading: mgrsLoading, refetch: refetchMgrs } =
    useFetch<ManagerApprovalStatus>(API.payroll.managerApprovals(cycleId));

  const approvalLevels = settings?.approval_levels ?? "L1";
  const isL1L2         = approvalLevels === "L1_L2";

  const isL1Done   = !!cycle?.attendance_l1_approved_at;
  const isL2Done   = !!cycle?.attendance_l2_approved_at;
  const isApproved = cycle?.status === "attendance_approved";

  const approvedCount     = mgrs?.approved_count ?? 0;
  const totalCount        = mgrs?.total_count ?? 0;
  const allMgrsApproved   = mgrs?.all_approved ?? false;
  const myRowPending      = mgrs?.current_user_pending ?? false;
  const noManagersSeeded  = totalCount === 0;

  function refetchAll() { refetchCycle(); refetchMgrs(); }

  if (cycleLoading || mgrsLoading) {
    return (
      <div className="card" style={{ padding: "40px", textAlign: "center", color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2 animate-spin" style={{ fontSize: 28 }} />
        <div style={{ marginTop: 8 }}>Loading approval status…</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-user-check" /> Attendance Approval Gate</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {isApproved
            ? <span className="badge badge-success"><i className="ti ti-check" /> Approved</span>
            : <span className="badge badge-warn"><i className="ti ti-clock" /> Pending</span>}
          <span className="badge badge-info">{isL1L2 ? "L1 + L2 required" : "L1 only"}</span>
          <button className="btn btn-ghost btn-sm" onClick={refetchAll} title="Refresh status">
            <i className="ti ti-refresh" />
          </button>
        </div>
      </div>

      <div className="card-body">

        {isApproved && (
          <div className="alert alert-success" style={{ marginBottom: 20 }}>
            <i className="ti ti-circle-check" />
            <span>All approvals complete. You can now proceed to compute payroll.</span>
          </div>
        )}

        {/* ── L1 section ─────────────────────────────────────────────────── */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: isL1Done ? "var(--success)" : "var(--warn)",
                color: "#fff", fontSize: 14,
              }}>
                {isL1Done
                  ? <i className="ti ti-check" />
                  : <span style={{ fontWeight: 700 }}>1</span>}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>Manager Approval (L1)</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  Each manager must sign off on their team's attendance
                </div>
              </div>
            </div>
            {!noManagersSeeded && (
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                <span style={{ color: isL1Done ? "var(--success)" : approvedCount > 0 ? "var(--warn)" : "var(--on-variant)" }}>
                  {approvedCount}
                </span>
                <span style={{ color: "var(--on-variant)" }}> / {totalCount} approved</span>
              </div>
            )}
          </div>

          {/* Progress bar */}
          {!noManagersSeeded && totalCount > 0 && (
            <div style={{ height: 6, borderRadius: 99, background: "var(--bg-high)", marginBottom: 14, overflow: "hidden" }}>
              <div style={{
                height: "100%", borderRadius: 99,
                width: `${(approvedCount / totalCount) * 100}%`,
                background: isL1Done ? "var(--success)" : "var(--primary)",
                transition: "width 0.4s ease",
              }} />
            </div>
          )}

          {/* Per-manager rows */}
          {noManagersSeeded ? (
            /* No managers with can_manage_team — HR direct approval */
            <div style={{
              border: `1.5px solid ${isL1Done ? "var(--success)" : "var(--warn)"}`,
              borderRadius: "var(--radius)", padding: "14px 16px",
              background: isL1Done ? "transparent" : "rgba(234,179,8,0.06)",
            }}>
              <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 10 }}>
                <i className="ti ti-info-circle" style={{ marginRight: 6 }} />
                No managers with team management rights are configured — HR can approve directly.
              </div>
              {isL1Done ? (
                <div style={{ fontSize: 12, color: "var(--success)" }}>
                  <i className="ti ti-circle-check" style={{ marginRight: 6 }} />
                  Approved by <strong>{cycle?.l1_approver_name}</strong> on {fmt(cycle?.attendance_l1_approved_at)}
                </div>
              ) : (
                <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
                  <i className="ti ti-info-circle" style={{ marginRight: 6 }} />
                  Approval happens on the Team Approvals page, not here — go to{" "}
                  <strong>HR Ops → Approvals → Attendance Approval</strong> to sign off.
                </div>
              )}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(mgrs?.approvals ?? []).map(row => {
                const isApprovedRow = !!row.approved_at;
                return (
                  <div
                    key={row.id}
                    style={{
                      display: "flex", alignItems: "flex-start", gap: 12,
                      padding: "10px 14px", borderRadius: "var(--radius)",
                      border: `1.5px solid ${isApprovedRow ? "var(--success)" : "var(--outline-v)"}`,
                      background: isApprovedRow ? "transparent" : "var(--bg-low)",
                    }}
                  >
                    <div style={{
                      width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      background: isApprovedRow ? "var(--success)" : "var(--bg-high)",
                      color: isApprovedRow ? "#fff" : "var(--on-variant)",
                      fontSize: 13,
                    }}>
                      {isApprovedRow
                        ? <i className="ti ti-check" />
                        : <i className="ti ti-clock" />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{row.manager_name}</span>
                        <span className={isApprovedRow ? "badge badge-success" : "badge badge-neutral"}>
                          {isApprovedRow ? "Approved" : "Pending"}
                        </span>
                      </div>
                      {isApprovedRow && (
                        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 2 }}>
                          {fmt(row.approved_at)}
                          {row.note && <span style={{ marginLeft: 8, fontStyle: "italic" }}>"{row.note}"</span>}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Current user's row still pending — direct them to Team Approvals, not here */}
              {myRowPending && !isL1Done && (
                <div style={{
                  padding: "14px 16px", borderRadius: "var(--radius)",
                  border: "1.5px solid var(--primary)", background: "rgba(30,78,140,0.06)",
                  marginTop: 4,
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>
                    <i className="ti ti-user-check" style={{ marginRight: 6 }} />
                    Your sign-off is required — approve it from{" "}
                    <strong>HR Ops → Approvals → Attendance Approval</strong>.
                  </div>
                </div>
              )}

              {!myRowPending && !isL1Done && !allMgrsApproved && (
                <div className="alert alert-info" style={{ marginTop: 4 }}>
                  <i className="ti ti-info-circle" />
                  <span>Waiting for other managers to approve. Refresh to check latest status.</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Connector between L1 and L2 */}
        {isL1L2 && (
          <div style={{ width: 2, height: 20, background: isL1Done ? "var(--success)" : "var(--outline-v)", margin: "0 0 24px 16px" }} />
        )}

        {/* ── L2 section ─────────────────────────────────────────────────── */}
        {isL1L2 && (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
                display: "flex", alignItems: "center", justifyContent: "center",
                background: isL2Done ? "var(--success)" : isL1Done ? "var(--warn)" : "var(--bg-high)",
                color: isL2Done || isL1Done ? "#fff" : "var(--on-variant)", fontSize: 14,
              }}>
                {isL2Done
                  ? <i className="ti ti-check" />
                  : <span style={{ fontWeight: 700 }}>2</span>}
              </div>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, color: isL1Done ? "var(--on-bg)" : "var(--on-variant)" }}>
                  HR Approval (L2)
                </div>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  HR verifies and signs off — unlocks payroll processing
                </div>
              </div>
            </div>

            <div style={{
              padding: "14px 16px", borderRadius: "var(--radius)",
              border: `1.5px solid ${isL2Done ? "var(--success)" : isL1Done ? "var(--warn)" : "var(--outline-v)"}`,
              background: !isL1Done ? "var(--bg-low)" : isL1Done && !isL2Done ? "rgba(234,179,8,0.06)" : "transparent",
              opacity: isL1Done ? 1 : 0.6,
            }}>
              {isL2Done ? (
                <div style={{ fontSize: 12, color: "var(--success)" }}>
                  <i className="ti ti-circle-check" style={{ marginRight: 6 }} />
                  Approved by <strong>{cycle?.l2_approver_name}</strong> on {fmt(cycle?.attendance_l2_approved_at)}
                </div>
              ) : !isL1Done ? (
                <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
                  <i className="ti ti-lock" style={{ marginRight: 6 }} />
                  Waiting for all managers (L1) to approve first
                </div>
              ) : (
                <>
                  <div style={{ fontSize: 13, marginBottom: 12 }}>
                    All {totalCount > 0 ? totalCount : ""} manager(s) have approved.
                    HR sign-off is the final step before payroll can be processed.
                  </div>
                  <div className="alert alert-info" style={{ marginTop: 0 }}>
                    <i className="ti ti-info-circle" />
                    <span>
                      Waiting for HR to sign off from{" "}
                      <strong>HR Ops → Approvals → Attendance Approval</strong> — not done here.
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

      </div>

      <div style={{ padding: "16px 20px", borderTop: "1px solid var(--outline-v)", display: "flex", justifyContent: "space-between", gap: 10 }}>
        <div>
          {cycle && (
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              Cycle: {cycle.cycle_start} → {cycle.cycle_end} · Pay date: {cycle.pay_date}
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" onClick={onBack}><i className="ti ti-arrow-left" /> Back</button>
          <button
            className="btn btn-filled"
            onClick={onNext}
            disabled={!isApproved}
            style={{ opacity: isApproved ? 1 : 0.5 }}
          >
            Continue <i className="ti ti-arrow-right" />
          </button>
        </div>
      </div>
    </div>
  );
}
