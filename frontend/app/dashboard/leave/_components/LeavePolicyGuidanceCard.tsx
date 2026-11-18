"use client";

// Real links only: the policy document comes from the existing Document
// Center filtered to category=policy (same reuse PoliciesAssetsTab.tsx
// already relies on — no dedicated "leave policy" model exists), and the
// "track" link deep-links to whichever of the employee's own leave requests
// is still pending, from the same /leave/requests/ list every other card
// on this page reads.

import type { CSSProperties } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { DOCUMENTS_BASE, type ApiDocument } from "../../documents/_data";
import { LeaveRequest, PaginatedResponse, fmtShortDate } from "../_data";

interface PagedResponse<T> { results: T[]; count: number }

export default function LeavePolicyGuidanceCard() {
  const { data: policyPage } = useFetch<PagedResponse<ApiDocument>>(
    `${DOCUMENTS_BASE}?category=policy&page_size=1`
  );
  const { data: requests } = useFetch<PaginatedResponse<LeaveRequest>>(API.leave.requests);

  const policyDoc = policyPage?.results?.[0] ?? null;
  const pending = (requests?.results ?? [])
    .filter(r => r.status === "pending" || r.status === "l2_pending")
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())[0] ?? null;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title"><i className="ti ti-file-info" /> Leave policy guidance</div>
          <div className="page-sub" style={{ marginTop: 2 }}>
            Balances and approval requirements vary by entity and employment type.
          </div>
        </div>
      </div>
      <div className="card-body">
        <div className="lv-links">
          {policyDoc ? (
            <a href={policyDoc.file_url} target="_blank" rel="noopener noreferrer" className="lv-link">
              <span className="lv-icon"><i className="ti ti-file-text" /></span>
              <span>Read leave policy<small>Opens the policy document</small></span>
            </a>
          ) : (
            <div className="lv-link is-muted">
              <span className="lv-icon" style={{ "--lv-accent": "#6b7280" } as CSSProperties}><i className="ti ti-file-off" /></span>
              <span>No leave policy document has been uploaded yet.</span>
            </div>
          )}

          {pending ? (
            <a href={`/dashboard/my-requests?tab=leave&request=${pending.id}`} className="lv-link">
              <span className="lv-icon"><i className="ti ti-progress" /></span>
              <span>Track {fmtShortDate(pending.start_date)} request<small>See who still has to approve it</small></span>
            </a>
          ) : (
            <div className="lv-link is-muted">
              <span className="lv-icon" style={{ "--lv-accent": "#6b7280" } as CSSProperties}><i className="ti ti-progress-check" /></span>
              <span>No pending leave request to track right now.</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
