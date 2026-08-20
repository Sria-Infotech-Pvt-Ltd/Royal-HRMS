"use client";

import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { Company, DashboardStats, PlatformAdminInfo } from "@/types/platformAdmin";

const AVATAR_TINTS = [
  { bg: "rgba(30, 78, 140, 0.12)", fg: "var(--primary)" },
  { bg: "var(--sec-c)",            fg: "var(--secondary)" },
  { bg: "var(--success-c)",        fg: "var(--success)" },
  { bg: "var(--info-c)",           fg: "var(--info)" },
];

export default function PlatformAdminDashboard() {
  const { data: me } = useFetch<PlatformAdminInfo>(API.platformAdmin.me, platformAdminApi);
  const { data: stats, loading, error } = useFetch<DashboardStats>(API.platformAdmin.dashboardStats, platformAdminApi);

  return (
    <div style={{ padding: "32px 24px" }}>
      <div
        style={{
          position: "relative", overflow: "hidden", borderRadius: "var(--radius-lg)",
          background: "linear-gradient(135deg, var(--primary) 0%, #12213b 100%)",
          padding: "26px 32px", marginBottom: 24, color: "#fff",
        }}
      >
        <i
          className="ti ti-building"
          style={{ position: "absolute", right: 20, top: "50%", transform: "translateY(-50%)", fontSize: 128, opacity: 0.1 }}
          aria-hidden
        />
        <div style={{ position: "relative" }}>
          <div style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", opacity: 0.75, marginBottom: 8 }}>
            Platform Admin
          </div>
          <h1 style={{ fontSize: 23, fontWeight: 700 }}>
            Welcome back{me?.full_name ? `, ${me.full_name.split(" ")[0]}` : ""}
          </h1>
          <p style={{ fontSize: 13, opacity: 0.85, marginTop: 4 }}>
            {stats ? `${stats.total_companies} ${stats.total_companies === 1 ? "company" : "companies"} under management` : "Loading your companies…"}
          </p>
        </div>
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
            <KpiCard label="Total companies" value={stats.total_companies} icon="ti-building" tint="si-primary" accent="var(--primary)" />
            <KpiCard label="Active" value={stats.active_companies} icon="ti-circle-check" tint="si-success" accent="var(--success)" />
            <KpiCard label="Disabled" value={stats.disabled_companies} icon="ti-circle-x" tint="si-info" accent="var(--info)" />
            <KpiCard
              label="Dormant" value={stats.dormant_company_count} icon="ti-clock-pause" tint="si-warn" accent="var(--warn)"
              sub="30+ days inactive"
            />
          </div>

          <div className="card pa-hover" style={{ marginBottom: 24 }}>
            <div className="card-header">
              <div className="card-title"><i className="ti ti-chart-donut" /> Provisioning status</div>
            </div>
            <div className="card-body">
              <ProvisioningBar provisioning={stats.provisioning} />
              <div style={{ display: "flex", gap: 32, marginTop: 18 }}>
                <ProvisioningRow icon="ti-circle-check" color="var(--success)" label="Active" count={stats.provisioning.active} />
                <ProvisioningRow icon="ti-clock-hour-4" color="var(--warn)" label="Pending" count={stats.provisioning.pending} />
                <ProvisioningRow icon="ti-alert-circle" color="var(--error)" label="Failed" count={stats.provisioning.failed} />
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

          <div className="card pa-hover" style={{ marginBottom: 24 }}>
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
                    {stats.company_usage.map((u, i) => {
                      const dormant = isDormant(u.last_activity_at);
                      return (
                        <tr key={u.company_code}>
                          <td>
                            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                              <CompanyAvatar name={u.company_name} index={i} />
                              <span>
                                {u.company_name}{" "}
                                <span className="badge badge-neutral" style={{ marginLeft: 4 }}>{u.company_code}</span>
                              </span>
                            </div>
                          </td>
                          <td style={{ fontVariantNumeric: "tabular-nums" }}>{u.employee_count}</td>
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

          <div className="card pa-hover">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-clock" /> Recently created</div>
              <a href="/platform-admin/companies" style={{ fontSize: 12.5 }}>View all →</a>
            </div>
            {stats.recent_companies.length === 0 ? (
              <p className="text-muted" style={{ fontSize: 13, padding: "0 20px 20px" }}>No companies yet.</p>
            ) : (
              <div>
                {stats.recent_companies.map((c, i) => (
                  <RecentCompanyRow key={c.id} company={c} index={i} />
                ))}
              </div>
            )}
          </div>
        </>
      ) : null}

      <style jsx>{`
        .pa-hover { transition: box-shadow 0.15s ease, transform 0.15s ease; }
        .pa-hover:hover { box-shadow: var(--shadow-md); }
        @media (prefers-reduced-motion: reduce) {
          .pa-hover { transition: none; }
        }
      `}</style>
    </div>
  );
}

function KpiCard({
  label, value, icon, tint, accent, sub,
}: { label: string; value: number; icon: string; tint: string; accent: string; sub?: string }) {
  return (
    <div className="stat-card pa-kpi" style={{ borderTop: `3px solid ${accent}` }}>
      <div>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {sub && <div className="stat-sub">{sub}</div>}
      </div>
      <div className={`stat-icon ${tint}`}><i className={`ti ${icon}`} /></div>
      <style jsx>{`
        .pa-kpi { transition: box-shadow 0.15s ease, transform 0.15s ease; }
        .pa-kpi:hover { box-shadow: var(--shadow-md); transform: translateY(-2px); }
        @media (prefers-reduced-motion: reduce) {
          .pa-kpi { transition: none; }
          .pa-kpi:hover { transform: none; }
        }
      `}</style>
    </div>
  );
}

function ProvisioningBar({ provisioning }: { provisioning: DashboardStats["provisioning"] }) {
  const total = provisioning.active + provisioning.pending + provisioning.failed;
  if (total === 0) {
    return <div style={{ height: 10, borderRadius: 5, background: "var(--bg-mid)" }} />;
  }
  const segments: { count: number; color: string; label: string }[] = [
    { count: provisioning.active,  color: "var(--success)", label: "Active" },
    { count: provisioning.pending, color: "var(--warn)",    label: "Pending" },
    { count: provisioning.failed,  color: "var(--error)",   label: "Failed" },
  ].filter(s => s.count > 0);
  return (
    <div style={{ display: "flex", height: 10, borderRadius: 5, overflow: "hidden", gap: 2 }}>
      {segments.map((s, i) => (
        <div
          key={i}
          title={`${s.label}: ${s.count}`}
          style={{ width: `${(s.count / total) * 100}%`, background: s.color }}
        />
      ))}
    </div>
  );
}

function ProvisioningRow({ icon, color, label, count }: { icon: string; color: string; label: string; count: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
      <i className={`ti ${icon}`} style={{ color, fontSize: 15 }} />
      <span style={{ color: "var(--on-bg)" }}>{label}</span>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{count}</strong>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function CompanyAvatar({ name, index }: { name: string; index: number }) {
  const tint = AVATAR_TINTS[index % AVATAR_TINTS.length];
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
        background: tint.bg, color: tint.fg, fontSize: 11, fontWeight: 700,
      }}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

function RecentCompanyRow({ company, index }: { company: Company; index: number }) {
  return (
    <div
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13,
        padding: "12px 20px", borderBottom: "1px solid var(--bg-high)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <CompanyAvatar name={company.company_name} index={index} />
        <span>
          <strong>{company.company_name}</strong>{" "}
          <span className="badge badge-neutral" style={{ marginLeft: 4 }}>{company.company_code}</span>
        </span>
      </div>
      <span className="text-muted" style={{ fontSize: 12 }}>
        {new Date(company.created_at).toLocaleDateString()}
      </span>
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
