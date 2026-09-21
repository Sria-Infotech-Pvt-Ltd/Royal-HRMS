"use client";

// Self-service "Policies & assets" — three read surfaces plus one write path:
//
// - Company policies: real policy documents from the existing Document
//   Center (GET /documents/?category=policy — apps/accounts/views.py:
//   DocumentListCreateView.get, already open to any authenticated user).
//   No dedicated "policy" model/endpoint exists, so this reuses that data
//   rather than inventing a second policy list.
// - Assigned assets: read-only view of company assets issued to the current
//   employee, via the existing GET /onboarding/assets/ endpoint (see
//   AssignedAssetsCard below for why no backend change was needed there).
// - Asset requests: a NEW asset an employee wants issued has no backing
//   model of its own. Rather than add a dedicated Django app/model for a
//   single free-text request, this reuses the existing generic HR Help
//   support-request model (apps/hrms/models.py:HRHelpRequest) with a new
//   'asset_request' topic choice — same pattern every other HR Help topic
//   already follows, and it comes with a list/detail endpoint, status
//   workflow, and permission-scoped visibility for free.
// - Policy quick reference: static illustrative guidance only (explicitly
//   called out in the design as demo copy, not sourced from any policy
//   engine).

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { DOCUMENTS_BASE, CATEGORY_META, type ApiDocument } from "../../documents/_data";
import { formatDate } from "@/lib/formatDate";
import AssetRequestModal, { type ApiHrHelpRequestLite, ASSET_REQUEST_TOPIC } from "./AssetRequestModal";

interface ApiAsset {
  id: string;
  asset_type: string;
  asset_type_display: string;
  tag_number: string;
  condition: string;
  issued_at: string;
  returned_at: string;
}
interface PagedResponse<T> { results: T[]; count: number }

const CONDITION_LABEL: Record<string, string> = {
  new: "New", good: "Good", refurbished: "Refurbished",
};
const STATUS_BADGE: Record<string, string> = {
  open: "badge-warn", in_progress: "badge-info", resolved: "badge-success",
};

interface Props {
  onNavigateToDocuments: () => void;
}

export default function PoliciesAssetsTab({ onNavigateToDocuments }: Props) {
  const [isRequestModalOpen, setIsRequestModalOpen] = useState(false);

  const { data: assets, loading: assetsLoading, error: assetsError } =
    useFetch<ApiAsset[]>(API.onboarding.assets);
  const { data: policyPage, loading: policiesLoading, error: policiesError } =
    useFetch<PagedResponse<ApiDocument>>(`${DOCUMENTS_BASE}?category=policy&page_size=10`);
  const { data: requestPage, loading: requestsLoading, error: requestsError, refetch: refetchRequests } =
    useFetch<PagedResponse<ApiHrHelpRequestLite>>(`${API.hrHelp.list}?page_size=50`);

  const assetList = assets ?? [];
  const policyList = policyPage?.results ?? [];
  const assetRequests = (requestPage?.results ?? []).filter(r => r.topic === ASSET_REQUEST_TOPIC);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 20 }}>Policies &amp; assets</h2>
          <p style={{ margin: "4px 0 0", fontSize: 13, color: "var(--on-variant)" }}>
            Company policies, your issued equipment, and asset requests.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => setIsRequestModalOpen(true)}>
          <i className="ti ti-plus" /> Request an asset
        </button>
      </div>

      <CompanyPoliciesCard
        policies={policyList}
        loading={policiesLoading}
        error={policiesError}
        onNavigateToDocuments={onNavigateToDocuments}
      />
      <AssignedAssetsCard assets={assetList} loading={assetsLoading} error={assetsError} />
      <AssetRequestsCard requests={assetRequests} loading={requestsLoading} error={requestsError} />
      <PolicyQuickReferenceGrid />

      {isRequestModalOpen && (
        <AssetRequestModal
          onClose={() => setIsRequestModalOpen(false)}
          onSubmitted={() => { setIsRequestModalOpen(false); refetchRequests(); }}
        />
      )}
    </div>
  );
}

function CompanyPoliciesCard({ policies, loading, error, onNavigateToDocuments }: {
  policies: ApiDocument[]; loading: boolean; error: string | null; onNavigateToDocuments: () => void;
}) {
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="card-title"><i className="ti ti-file-text" /> Company policies</div>
        <button className="btn btn-ghost btn-sm" onClick={onNavigateToDocuments}>
          <i className="ti ti-folder" /> Document Center
        </button>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading policies…</h3>
        </div>
      ) : policies.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-file-text" />
          <h3>No policy documents yet</h3>
          <p>Policy documents uploaded to the Document Center will appear here.</p>
        </div>
      ) : (
        <div style={{ padding: "4px 24px 16px" }}>
          {policies.map(doc => (
            <div key={doc.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 0", borderBottom: "1px solid var(--outline-variant)", gap: 12 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{doc.title}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {CATEGORY_META[doc.category].label} · Effective {formatDate(doc.updated_at || doc.uploaded_at)}
                </div>
              </div>
              <a className="btn btn-ghost btn-sm" href={doc.file_url} target="_blank" rel="noreferrer">
                <i className="ti ti-download" /> Download
              </a>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function AssignedAssetsCard({ assets, loading, error }: {
  assets: ApiAsset[]; loading: boolean; error: string | null;
}) {
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-device-laptop" /> Assigned assets</div>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading assets…</h3>
        </div>
      ) : assets.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-device-laptop" />
          <h3>No assets issued yet</h3>
          <p>Equipment issued to you (laptop, phone, access card) will be listed here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Asset</th>
                <th>Tag / Serial</th>
                <th>Condition</th>
                <th>Issued</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {assets.map(a => (
                <tr key={a.id}>
                  <td style={{ fontWeight: 600 }}>{a.asset_type_display}</td>
                  <td>{a.tag_number || "—"}</td>
                  <td>{CONDITION_LABEL[a.condition] ?? a.condition}</td>
                  <td style={{ color: "var(--on-variant)" }}>{formatDate(a.issued_at) || "—"}</td>
                  <td>
                    <span className={`badge ${a.returned_at ? "badge-neutral" : "badge-success"}`}>
                      {a.returned_at ? "RETURNED" : "ASSIGNED"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AssetRequestsCard({ requests, loading, error }: {
  requests: ApiHrHelpRequestLite[]; loading: boolean; error: string | null;
}) {
  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header">
        <div className="card-title"><i className="ti ti-clipboard-list" /> Asset requests</div>
      </div>
      {error && <div className="alert alert-error" style={{ margin: "0 24px 16px" }}>{error}</div>}
      {loading ? (
        <div className="empty-state">
          <i className="ti ti-loader-2 spin" />
          <h3>Loading requests…</h3>
        </div>
      ) : requests.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-clipboard-list" />
          <h3>No asset requests yet</h3>
          <p>Requests submitted via &quot;Request an asset&quot; will be tracked here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Request</th>
                <th>Status</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {requests.map(r => (
                <tr key={r.id}>
                  <td style={{ maxWidth: 420 }}>{r.message}</td>
                  <td><span className={`badge ${STATUS_BADGE[r.status]}`}>{r.status_display}</span></td>
                  <td style={{ color: "var(--on-variant)" }}>{formatDate(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const QUICK_REFERENCE = [
  { icon: "ti-beach", title: "Leave", text: "Apply at least 2 days ahead where possible; carried-forward leave expires per policy." },
  { icon: "ti-clock", title: "Attendance", text: "Clock in/out within the geofenced radius; corrections need a manager's approval." },
  { icon: "ti-receipt", title: "Expenses", text: "Attach a receipt for every claim over the category's no-receipt threshold." },
  { icon: "ti-device-laptop", title: "Assets", text: "Report a lost or damaged asset to HR immediately to avoid recovery charges." },
];

function PolicyQuickReferenceGrid() {
  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-info-circle" /> Policy quick reference</div>
      </div>
      <p style={{ margin: "0 24px 8px", fontSize: 12, color: "var(--on-variant)" }}>
        Illustrative demo guidance only — refer to the documents above for the current policy.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, padding: "8px 24px 24px" }}>
        {QUICK_REFERENCE.map(tile => (
          <div key={tile.title} style={{ border: "1px solid var(--outline-variant)", borderRadius: 10, padding: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontWeight: 600, fontSize: 13 }}>
              <i className={`ti ${tile.icon}`} /> {tile.title}
            </div>
            <p style={{ margin: 0, fontSize: 12, color: "var(--on-variant)" }}>{tile.text}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
