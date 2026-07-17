"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { fmtDate, initials } from "../interview-list/_data";
import OnboardingDrawer, { ApprovalUser } from "./_components/OnboardingDrawer";

export default function CandidateReviewPage() {
  const router       = useRouter();
  const canApprove   = usePermission("employees.approve");

  const [rows,    setRows]    = useState<ApprovalUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  const [drawer,    setDrawer]    = useState<ApprovalUser | null>(null);
  const [remarks,   setRemarks]   = useState("");
  const [acting,    setActing]    = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const res = await clientApi.get(API.onboarding.approvals);
      setRows(res.data?.data?.results ?? []);
    } catch {
      setError("Failed to load onboarding submissions.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  async function handleOnboardingAction(
    userId: string,
    decision: "approve" | "reject",
    extras?: { department: string; designation: string; assessmentId?: string },
  ) {
    setActing(true); setActionErr(null);
    try {
      await clientApi.post(API.onboarding.approve(userId), {
        decision,
        remarks,
        department:  extras?.department,
        designation: extras?.designation,
      });
      if (decision === "approve" && extras?.assessmentId && drawer?.candidate_id) {
        try {
          await clientApi.post(API.assessments.assign, {
            candidate_id:  drawer.candidate_id,
            assessment_id: extras.assessmentId,
          });
        } catch {
          // Approval already succeeded — assessment assignment failure is non-blocking
        }
      }
      setDrawer(null); setRemarks("");
      if (decision === "approve") {
        router.push("/dashboard/employees");
      } else {
        loadAll();
      }
    } catch (err: unknown) {
      setActionErr((err as { message?: string })?.message ?? "Action failed.");
    } finally {
      setActing(false);
    }
  }

  const STATUS_MAP: Record<string, [string, string]> = {
    submitted: ["Submitted",      "badge-warn"   ],
    approved:  ["Approved",       "badge-success"],
    rejected:  ["Needs Revision", "badge-error"  ],
  };

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Onboarding Approvals</div>
          <div className="page-sub">Review and approve employee onboarding submissions</div>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ marginBottom: 20 }}>
        {[
          { label: "Total",        value: rows.length,                                                       icon: "ti-users",     iconCls: "si-primary" },
          { label: "Pending",      value: rows.filter(r => r.onboarding_status === "submitted").length,      icon: "ti-eye",       iconCls: "si-warn"    },
          { label: "Approved",     value: rows.filter(r => r.onboarding_status === "approved").length,       icon: "ti-check",     iconCls: "si-success" },
          { label: "Needs Revision", value: rows.filter(r => r.onboarding_status === "rejected").length,    icon: "ti-refresh",   iconCls: "si-error"   },
        ].map(s => (
          <div key={s.label} className="stat-card">
            <div className={`stat-icon ${s.iconCls}`}><i className={`ti ${s.icon}`} /></div>
            <div className="stat-label">{s.label}</div>
            <div className="stat-value">{s.value}</div>
          </div>
        ))}
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

      {loading ? (
        <div className="text-center py-16"><i className="ti ti-loader-2 spin text-3xl" /></div>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-user-plus" />
          <h3>No onboarding submissions</h3>
          <p>Onboarding submissions from new employees will appear here.</p>
        </div>
      ) : (
        <div className="card" style={{ overflow: "visible" }}>
          <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
            <table className="data-table" style={{ minWidth: 560 }}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="col-hide-sm">Role / Designation</th>
                  <th className="col-hide-md">Branch</th>
                  <th className="col-hide-md">Joined</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => {
                  const [statusLabel, statusCls] = STATUS_MAP[row.onboarding_status] ?? ["Pending", "badge-neutral"];
                  return (
                    <tr key={row.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <div className="user-avatar" style={{ width: 32, height: 32, fontSize: 12, flexShrink: 0 }}>
                            {initials(row.full_name)}
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 600, fontSize: ".88rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>{row.full_name}</div>
                            <div style={{ fontSize: ".76rem", color: "var(--on-variant)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 160 }}>{row.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="col-hide-sm" style={{ fontSize: ".85rem" }}>{row.designation || "—"}</td>
                      <td className="col-hide-md" style={{ fontSize: ".85rem" }}>{row.branch || "—"}</td>
                      <td className="col-hide-md" style={{ fontSize: ".85rem" }}>{fmtDate(row.date_joined)}</td>
                      <td><span className={`badge ${statusCls}`} style={{ whiteSpace: "nowrap" }}>{statusLabel}</span></td>
                      <td>
                        {row.onboarding_status === "rejected" ? (
                          <span
                            className="badge badge-neutral"
                            title="Waiting for the employee to correct and resubmit"
                            style={{ cursor: "default", userSelect: "none" }}
                          >
                            Awaiting resubmission
                          </span>
                        ) : canApprove ? (
                          <button
                            className="btn btn-ghost btn-sm"
                            onClick={() => { setDrawer(row); setRemarks(""); setActionErr(null); }}
                          >
                            Review
                          </button>
                        ) : null}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <style>{`
        @media (max-width: 768px) { .col-hide-md { display: none; } }
        @media (max-width: 560px) { .col-hide-sm { display: none; } }
      `}</style>

      {drawer && (
        <OnboardingDrawer
          user={drawer}
          remarks={remarks}
          acting={acting}
          actionErr={actionErr}
          onRemarksChange={setRemarks}
          onAction={handleOnboardingAction}
          onClose={() => setDrawer(null)}
        />
      )}
    </>
  );
}
