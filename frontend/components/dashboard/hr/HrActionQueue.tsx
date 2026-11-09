"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useAnyPermission } from "@/hooks/usePermission";
import type { PaginatedResponse, SeparationRequest } from "@/types/separation";
import type { HRActionQueue, LeaveUpdatePayload } from "@/types/dashboard";
import type { PaginatedFaceRegistrations } from "@/types/faceRegistration";

// The server-computed queue plus the counts this component reads from the workflow lists that have their own endpoints.
type QueueData = HRActionQueue & { face_registrations: number; wfh_requests: number };

const ROWS: { key: keyof Omit<QueueData, "total_pending">; label: string; icon: string; href: string }[] = [
  { key: "candidate_reviews",      label: "Candidate Reviews",       icon: "ti-user-search",  href: "/dashboard/candidate-review" },
  { key: "leave_approvals",        label: "Leave Approvals",         icon: "ti-calendar-off", href: "/dashboard/approvals"        },
  { key: "attendance_corrections", label: "Attendance Corrections",  icon: "ti-clock-edit",   href: "/dashboard/approvals"        },
  { key: "wfh_requests",           label: "Work From Home Requests", icon: "ti-home-2",      href: "/dashboard/approvals"        },
  { key: "face_registrations",     label: "Face ID Registrations",   icon: "ti-face-id",      href: "/dashboard/approvals"        },
  { key: "expense_claims",         label: "Expense Claims",          icon: "ti-receipt",      href: "/dashboard/expenses"        },
  { key: "onboarding_reviews",     label: "Onboarding Reviews",      icon: "ti-id-badge",     href: "/dashboard/employees"       },
  { key: "separation_requests",    label: "Separation Requests",     icon: "ti-user-minus",   href: "/dashboard/separation"       },
];

export default function HrActionQueue() {
  const { data: fetchedData, loading } = useFetch<HRActionQueue>(API.dashboard.hrActionQueue);
  // Live data pushed by the backend over WebSocket — takes priority over the
  // HTTP-fetched copy so the counts update instantly without a round trip.
  const [liveData, setLiveData] = useState<HRActionQueue | null>(null);
  const fetched = liveData ?? fetchedData;

  // The dashboard action-queue endpoint doesn't include separation counts
  // yet — read the count straight from the separation API's team scope
  // (everyone else's requests this viewer can act on) instead.
  const canApproveSeparation = useAnyPermission("separation.approve", "settings.edit");
  const { data: separationPage } = useFetch<PaginatedResponse<SeparationRequest>>(
    canApproveSeparation ? `${API.separation.list}?scope=team&page_size=1` : null,
  );
  const separationCount = separationPage?.count ?? 0;

  // Each of these is the workflow's own list, which the server already limits to what this person may see.
  const canApproveFace = useAnyPermission("facial_recognition.approve");
  const { data: facePage } = useFetch<PaginatedFaceRegistrations>(
    canApproveFace ? `${API.attendance.faceRegistration.pending}?page_size=1` : null,
  );
  const canApproveWfh = useAnyPermission("wfh.approve");
  const { data: wfhPage } = useFetch<{ count: number }>(
    canApproveWfh ? `${API.approvals.wfhRequests}?scope=team&status=pending,l2_pending&page_size=1` : null,
  );
  const faceCount = facePage?.count ?? 0;
  const wfhCount = wfhPage?.count ?? 0;

  const data: QueueData | null = fetched
    ? {
        ...fetched,
        separation_requests: separationCount, face_registrations: faceCount, wfh_requests: wfhCount,
        total_pending: fetched.total_pending + separationCount + faceCount + wfhCount,
      }
    : null;

  useEffect(() => {
    function handleLeaveUpdate(event: Event) {
      const { detail } = event as CustomEvent<LeaveUpdatePayload>;
      if (detail?.action_queue) {
        setLiveData(detail.action_queue);
      }
    }
    window.addEventListener("leave:updated", handleLeaveUpdate);
    return () => window.removeEventListener("leave:updated", handleLeaveUpdate);
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-checks" /> Action Queue</div>
        {!loading && data && data.total_pending > 0 && (
          <span className="badge badge-error">{data.total_pending} pending</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : (
        <div style={{ padding: "4px 0 8px" }}>
          {ROWS.map(row => {
            const count = data?.[row.key] ?? 0;
            const isEmpty = count === 0;
            return (
              <Link
                key={row.key}
                href={row.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "9px 20px",
                  textDecoration: "none",
                  transition: "background 0.15s",
                  opacity: isEmpty ? 0.45 : 1,
                  pointerEvents: isEmpty ? "none" : "auto",
                }}
                className="action-row"
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <i className={`ti ${row.icon}`} style={{ fontSize: 15, color: isEmpty ? "var(--on-variant)" : "var(--primary)", width: 18 }} />
                  <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{row.label}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {count > 0 && (
                    <span style={{
                      minWidth: 22, height: 22, borderRadius: 11, background: "var(--error-solid)",
                      color: "#fff", fontSize: 11, fontWeight: 700,
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      padding: "0 6px",
                    }}>{count}</span>
                  )}
                  <i className="ti ti-chevron-right" style={{ fontSize: 13, color: "var(--on-variant)" }} />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
