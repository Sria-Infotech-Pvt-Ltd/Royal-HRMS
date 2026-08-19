"use client";

import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { MODULE_LABELS } from "@/types/platformAdmin";
import type { DashboardStats, PlatformAdminInfo } from "@/types/platformAdmin";

export default function PlatformAdminDashboard() {
  const { data: me } = useFetch<PlatformAdminInfo>(API.platformAdmin.me, platformAdminApi);
  const { data: stats, loading, error } = useFetch<DashboardStats>(API.platformAdmin.dashboardStats, platformAdminApi);

  return (
    <div style={{ padding: "32px 24px" }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Dashboard</h1>
        {me && <p className="text-muted" style={{ fontSize: 13 }}>Signed in as {me.full_name || me.email}</p>}
      </div>

      {loading ? (
        <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" /> Loading dashboard…
        </div>
      ) : error ? (
        <div className="alert alert-warn"><i className="ti ti-alert-triangle" /><div>{error}</div></div>
      ) : stats ? (
        <>
          <div className="stats-grid mb-6">
            <div className="stat-card">
              <div>
                <div className="stat-label">Total companies</div>
                <div className="stat-value">{stats.total_companies}</div>
              </div>
              <div className="stat-icon si-primary"><i className="ti ti-building" /></div>
            </div>
            <div className="stat-card">
              <div>
                <div className="stat-label">Active</div>
                <div className="stat-value">{stats.active_companies}</div>
              </div>
              <div className="stat-icon si-success"><i className="ti ti-circle-check" /></div>
            </div>
            <div className="stat-card">
              <div>
                <div className="stat-label">Disabled</div>
                <div className="stat-value">{stats.disabled_companies}</div>
              </div>
              <div className="stat-icon si-info"><i className="ti ti-circle-x" /></div>
            </div>
            <div className="stat-card">
              <div>
                <div className="stat-label">Dormant</div>
                <div className="stat-value">{stats.dormant_company_count}</div>
                <div className="stat-sub">30+ days inactive</div>
              </div>
              <div className="stat-icon si-warn"><i className="ti ti-clock-pause" /></div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 24 }}>
            <div className="card">
              <div className="card-header">
                <div className="card-title"><i className="ti ti-chart-donut" /> Provisioning status</div>
              </div>
              <div className="card-body">
                <ProvisioningBar provisioning={stats.provisioning} />
                <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 16 }}>
                  <ProvisioningRow label="Active" badgeClass="badge-success" count={stats.provisioning.active} />
                  <ProvisioningRow label="Pending" badgeClass="badge-warn" count={stats.provisioning.pending} />
                  <ProvisioningRow label="Failed" badgeClass="badge-error" count={stats.provisioning.failed} />
                </div>
                {(stats.provisioning.pending > 0 || stats.provisioning.failed > 0) && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--outline-v)" }}>
                    {stats.provisioning.pending > 0 && (
                      <a href="/platform-admin/companies" style={{ fontSize: 12.5 }}>
                        View pending companies →
                      </a>
                    )}
                    {stats.provisioning.failed > 0 && (
                      <a href="/platform-admin/companies" className="text-error" style={{ fontSize: 12.5 }}>
                        {stats.provisioning.failed} failed — review and recreate →
                      </a>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="card">
              <div className="card-header">
                <div className="card-title"><i className="ti ti-puzzle" /> Module adoption</div>
              </div>
              <div className="card-body">
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                  {Object.entries(stats.module_adoption).map(([key, count]) => {
                    const pct = stats.total_companies ? Math.round((count / stats.total_companies) * 100) : 0;
                    return (
                      <div key={key}>
                        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12.5, marginBottom: 6 }}>
                          <span style={{ color: "var(--on-bg)", fontWeight: 500 }}>
                            {MODULE_LABELS[key as keyof typeof MODULE_LABELS] ?? key}
                          </span>
                          <span className="text-muted">{count} · {pct}%</span>
                        </div>
                        <div style={{ height: 6, borderRadius: 3, background: "var(--bg-mid)", overflow: "hidden" }}>
                          <div style={{ height: "100%", borderRadius: 3, background: "var(--primary)", width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

          <div className="card" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title"><i className="ti ti-activity" /> Company usage</div>
              {stats.dormant_company_count > 0 && (
                <span className="badge badge-warn">
                  {stats.dormant_company_count} dormant (30+ days, or never used)
                </span>
              )}
            </div>
            <div style={{ padding: "16px 20px 0" }}>
              <p className="text-muted" style={{ fontSize: 12.5, marginBottom: 4 }}>
                Real activity inside each company&apos;s own account — not just registry data. Dormant companies
                (paying but not logging in) surface first.
              </p>
            </div>
            {stats.company_usage.length === 0 ? (
              <p className="text-muted" style={{ fontSize: 13, padding: "0 20px 20px" }}>No fully-provisioned companies yet.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th>Employees</th>
                      <th>Last activity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.company_usage.map(u => {
                      const dormant = isDormant(u.last_activity_at);
                      return (
                        <tr key={u.company_code}>
                          <td>
                            {u.company_name}{" "}
                            <span className="badge badge-neutral" style={{ marginLeft: 6 }}>{u.company_code}</span>
                          </td>
                          <td>{u.employee_count}</td>
                          <td>
                            <span className={dormant ? "text-error" : undefined} style={{ fontSize: 13 }}>
                              {formatRelativeTime(u.last_activity_at)}
                            </span>
                            {dormant && <i className="ti ti-alert-triangle" style={{ marginLeft: 6, color: "var(--error)" }} />}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-clock" /> Recently created</div>
              <a href="/platform-admin/companies" style={{ fontSize: 12.5 }}>View all →</a>
            </div>
            {stats.recent_companies.length === 0 ? (
              <p className="text-muted" style={{ fontSize: 13, padding: "0 20px 20px" }}>No companies yet.</p>
            ) : (
              <div>
                {stats.recent_companies.map(c => (
                  <div
                    key={c.id}
                    style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13,
                      padding: "12px 20px", borderBottom: "1px solid var(--bg-high)",
                    }}
                  >
                    <div>
                      <strong>{c.company_name}</strong>{" "}
                      <span className="badge badge-neutral" style={{ marginLeft: 6 }}>{c.company_code}</span>
                    </div>
                    <span className="text-muted" style={{ fontSize: 12 }}>
                      {new Date(c.created_at).toLocaleDateString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}
    </div>
  );
}

function ProvisioningBar({ provisioning }: { provisioning: DashboardStats["provisioning"] }) {
  const total = provisioning.active + provisioning.pending + provisioning.failed;
  if (total === 0) {
    return <div style={{ height: 8, borderRadius: 4, background: "var(--bg-mid)" }} />;
  }
  const segments: { count: number; color: string }[] = [
    { count: provisioning.active, color: "var(--success)" },
    { count: provisioning.pending, color: "var(--warn)" },
    { count: provisioning.failed, color: "var(--error)" },
  ];
  return (
    <div style={{ display: "flex", height: 8, borderRadius: 4, overflow: "hidden", background: "var(--bg-mid)" }}>
      {segments.filter(s => s.count > 0).map((s, i) => (
        <div key={i} style={{ width: `${(s.count / total) * 100}%`, background: s.color }} />
      ))}
    </div>
  );
}

function ProvisioningRow({ label, badgeClass, count }: { label: string; badgeClass: string; count: number }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
      <span className={`badge ${badgeClass}`}>{label}</span>
      <strong>{count}</strong>
    </div>
  );
}

const DORMANT_DAYS = 30;

function isDormant(lastActivityAt: string | null): boolean {
  if (!lastActivityAt) return true;
  const ageMs = Date.now() - new Date(lastActivityAt).getTime();
  return ageMs > DORMANT_DAYS * 24 * 60 * 60 * 1000;
}

function formatRelativeTime(iso: string | null): string {
  if (!iso) return "No activity yet";
  const diffMs = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  return `${months} month${months === 1 ? "" : "s"} ago`;
}
