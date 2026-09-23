"use client";

import { Candidate, fmtDate, initials } from "@/app/dashboard/interview-list/_data";
import { STATUS_META } from "./_data";

export default function ReferralTable({
  candidates, loading, error, search, onSearch,
}: {
  candidates: Candidate[];
  loading: boolean;
  error: string | null;
  search: string;
  onSearch: (v: string) => void;
}) {
  const filtered = search
    ? candidates.filter(c =>
        `${c.name} ${c.position_applied} ${c.referral_by_name}`
          .toLowerCase().includes(search.toLowerCase()))
    : candidates;

  return (
    <>
      <div className="card-header">
        <span className="card-title">
          <i className="ti ti-users" /> {filtered.length} Referral{filtered.length !== 1 ? "s" : ""}
        </span>
        <div className="search-bar">
          <i className="ti ti-search" />
          <input placeholder="Search by name, position…" value={search}
            onChange={e => onSearch(e.target.value)} suppressHydrationWarning />
        </div>
      </div>

      {error && (
        <div className="alert alert-error" style={{ margin: "0 20px 12px" }}>
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      <div className="table-wrap">
        {loading ? (
          <div className="text-center py-10"><i className="ti ti-loader-2 spin text-3xl" /></div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-user-plus" />
            <h3>No referrals found</h3>
            <p>Try adjusting your search or submit a new referral.</p>
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Candidate</th><th>Position</th><th>Company Code</th>
                <th>Referred By</th><th>Status</th><th>Referred On</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(c => (
                <tr key={c.id}>
                  <td>
                    <div className="flex items-center gap-3">
                      <div className="user-avatar" style={{ width: 32, height: 32, fontSize: 12, flexShrink: 0 }}>
                        {initials(c.name)}
                      </div>
                      <div>
                        <strong>{c.name}</strong>
                        <div className="text-xs text-[var(--on-variant)]">{c.email}</div>
                        {c.phone && <div className="text-xs text-[var(--on-variant)]">{c.phone}</div>}
                      </div>
                    </div>
                  </td>
                  <td>{c.position_applied}</td>
                  <td>
                    {c.branch_name
                      ? <span className="badge badge-neutral" style={{ fontSize: 11 }}>{c.branch_name}</span>
                      : <span className="text-xs text-[var(--on-variant)]">—</span>}
                  </td>
                  <td>
                    {c.referral_by_name
                      ? <span style={{ fontSize: 12, color: "#7c3aed", display: "flex", alignItems: "center", gap: 4 }}>
                          <i className="ti ti-user-plus" style={{ fontSize: 11 }} />{c.referral_by_name}
                        </span>
                      : <span className="text-xs text-[var(--on-variant)]">—</span>}
                  </td>
                  <td>
                    <span className={`badge ${STATUS_META[c.status]?.cls ?? "badge-neutral"}`}>
                      {STATUS_META[c.status]?.label ?? c.status}
                    </span>
                  </td>
                  <td className="text-xs">{fmtDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
