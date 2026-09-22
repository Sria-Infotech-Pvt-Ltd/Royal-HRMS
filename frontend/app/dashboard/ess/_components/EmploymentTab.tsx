"use client";

// Self-service "Employment" tab (ESS -> Employment). Deliberately its own
// component rather than reusing app/dashboard/separation/page.tsx directly:
// that page is the shared HR/admin-facing Separation & Exit list (scope
// toggle, employee-code filter, table of everyone's requests) and is still
// reachable from its own sidebar entry — this tab is the narrower,
// employee-only "my assignment + my resignation request" view.
//
// "Current assignment" reads the same /employees/me/ endpoint
// ProfileSummaryTab.tsx uses. "Lifecycle requests" reads the employee's own
// separation requests (GET /separation/requests/ already scopes to the
// caller when no scope=team/employee_id is passed — see
// apps/hrms/views/separation.py). Resigning submits through
// ResignationRequestModal.tsx -> the same POST /separation/requests/ used
// elsewhere (profile/_components/SeparationCard.tsx, separation/page.tsx).

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import { fmtDate, statusBadgeClass } from "@/app/dashboard/separation/_workflow";
import type { PaginatedResponse, SeparationRequest } from "@/types/separation";
import ResignationRequestModal from "./ResignationRequestModal";

interface EmploymentProfileData {
  employee_id:                string;
  designation:                string;
  work_location:               string | null;
  branch:                      string;
  employment_status:            string | null;
  employment_status_display:    string;
  notice_period_days:           number | null;
  reporting_manager?:           { name: string | null } | null;
}

interface Props {
  onNavigateToDocuments: () => void;
}

export default function EmploymentTab({ onNavigateToDocuments }: Props) {
  const [showResign, setShowResign] = useState(false);

  const { data: profile } = useFetch<EmploymentProfileData>(API.employees.me);
  const { data: sepPage, loading: sepLoading, error: sepError, refetch: refetchSep } =
    useFetch<PaginatedResponse<SeparationRequest>>(`${API.separation.list}?page_size=5`);

  const requests = sepPage?.results ?? [];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>Employment &amp; lifecycle</h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>
            Review your current assignment and submit formal employment actions.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => setShowResign(true)}>
          <i className="ti ti-logout" /> Start resignation request
        </button>
      </div>

      <CurrentAssignmentCard profile={profile} />
      <EmploymentDocumentsCard onNavigateToDocuments={onNavigateToDocuments} />
      <LifecycleRequestsCard requests={requests} loading={sepLoading} error={sepError} />

      {showResign && (
        <ResignationRequestModal
          defaultNoticePeriodDays={profile?.notice_period_days ?? null}
          onClose={() => setShowResign(false)}
          onSubmitted={() => { setShowResign(false); refetchSep(); }}
        />
      )}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{value}</div>
    </div>
  );
}

function CurrentAssignmentCard({ profile }: { profile: EmploymentProfileData | null | undefined }) {
  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-id-badge-2" /> Current assignment</div>
      </div>
      <div style={{ padding: "4px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Tile label="EMPLOYMENT STATUS"    value={profile?.employment_status_display || "—"} />
        <Tile label="EMPLOYEE ID"          value={profile?.employee_id || "—"} />
        <Tile label="POSITION"             value={profile?.designation || "—"} />
        <Tile label="REPORTING MANAGER"    value={profile?.reporting_manager?.name || "—"} />
        <Tile label="LOCATION"             value={profile?.work_location || profile?.branch || "—"} />
        <Tile label="NOTICE PERIOD"        value={profile?.notice_period_days != null ? `${profile.notice_period_days} days` : "—"} />
      </div>
    </div>
  );
}

function EmploymentDocumentsCard({ onNavigateToDocuments }: { onNavigateToDocuments: () => void }) {
  return (
    <div className="card mb-16">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-file-certificate" /> Employment documents</div>
      </div>
      <div style={{ padding: "4px 24px 20px" }}>
        {/* Real on-demand PDF, generated server-side from the caller's own
            employee record and the actual Company letterhead config — see
            apps/accounts/services_employment_letter.py and
            MyEmploymentLetterPdfView. Content-Disposition: attachment forces
            the download, so no target="_blank" is needed. */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-v)", gap: 12 }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Employment verification letter</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>For bank, visa or tenancy verification</div>
          </div>
          <a
            href={`${API_BASE}${API.employees.myEmploymentLetterPdf}`}
            className="btn btn-ghost btn-sm"
          >
            <i className="ti ti-download" /> Download
          </a>
        </div>
        <button
          type="button"
          onClick={onNavigateToDocuments}
          style={{ width: "100%", textAlign: "left", background: "transparent", border: "none", cursor: "pointer", padding: "12px 0 0", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
        >
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: "var(--on-bg)" }}>All employee documents</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)" }}>Identity, education and company documents</div>
          </div>
          <i className="ti ti-chevron-right" style={{ color: "var(--on-variant)" }} />
        </button>
      </div>
    </div>
  );
}

function LifecycleRequestsCard({ requests, loading, error }: {
  requests: SeparationRequest[]; loading: boolean; error: string | null;
}) {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-list-check" /> Lifecycle requests</div>
      </div>
      <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
        Formal requests require manager and HR review; submitting does not change your status immediately.
      </p>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading…</h3>
        </div>
      ) : requests.length === 0 ? (
        // No pre-existing empty-state copy for this card (it is new) — this
        // second line was authored for this task, matching the tone of the
        // other ESS empty states in this file's siblings.
        <div className="empty-state">
          <i className="ti ti-list-check" />
          <h3>No lifecycle actions pending</h3>
          <p>Any resignation or employment letter request will appear here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Proposed last day</th>
                <th>Status</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 600 }}>{r.separation_type_display}</td>
                  <td>{fmtDate(r.proposed_last_working_day)}</td>
                  <td><span className={`badge ${statusBadgeClass(r.status)}`}>{r.status_display}</span></td>
                  <td style={{ color: "var(--on-variant)" }}>{fmtDate(r.request_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
