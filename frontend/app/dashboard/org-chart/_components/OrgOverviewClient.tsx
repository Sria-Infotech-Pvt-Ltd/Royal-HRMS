"use client";

import { useRouter } from "next/navigation";
import { useOrganizationOverview } from "@/hooks/useOrganizationOverview";
import { StatCard } from "@/components/dashboard/StatCard";
import OverviewList, { type OverviewListItem } from "@/components/dashboard/OverviewList";
import QuickActionsGrid from "@/components/dashboard/QuickActionsGrid";
import {
  BrandBanner, CapabilityGrid, OperationalToolsGrid, PlatformSafeguards, type TileDef,
} from "@/components/dashboard/ModuleOverviewKit";
import type { OrgOverviewRowStatusKind } from "@/types/organization";

const CHIP_TONE: Record<OrgOverviewRowStatusKind, "warn" | "success"> = {
  manager_vacancy: "warn",
  open_positions: "warn",
  headcount: "success",
};

export default function OrgOverviewClient({ onOpenChart }: { onOpenChart: (unitId?: string) => void }) {
  const router = useRouter();
  const { data, error } = useOrganizationOverview();

  const CAPABILITIES: TileDef[] = [
    { title: "Legal entities", desc: "Companies, registrations, establishments and statutory identities.", href: "/dashboard/settings/company" },
    { title: "Org hierarchy", desc: "Business units, divisions, departments, teams and reporting lines.", href: "#chart" },
    { title: "Position control", desc: "Sanctioned positions, vacancies, incumbents, bands and job families.", href: "#chart" },
    { title: "Assignment history", desc: "Effective-dated entity, unit, location, cost center and manager changes.", href: "#chart" },
    { title: "Workforce planning", desc: "Approved headcount, hiring demand, vacancy aging and capacity.", href: "/dashboard/reports" },
    { title: "Reorganizations", desc: "Model, approve and activate future organization structures.", href: "#chart" },
    { title: "Locations", desc: "Sites, remote zones, calendars, shifts and PT/LWF mappings.", href: "/dashboard/branches" },
    { title: "Cost allocation", desc: "Primary and split cost-center assignments for finance.", href: "#chart" },
  ];

  const OPERATIONAL_TOOLS: TileDef[] = [
    { title: "Create position", desc: "Add a budgeted or replacement position.", href: "#chart" },
    { title: "Move employee", desc: "Future-date a department, location or manager change.", href: "/dashboard/employees" },
    { title: "Reorganization planner", desc: "Model structural changes before activation.", href: "#chart" },
    { title: "Vacancy register", desc: "Review open, frozen and filled positions.", href: "#chart" },
    { title: "Org chart", desc: "Navigate solid and dotted reporting relationships.", href: "#chart" },
    { title: "Assignment audit", desc: "Compare current, past and future assignments.", href: "/dashboard/settings/audit" },
  ];

  function go(href: string) {
    if (href === "#chart") onOpenChart();
    else router.push(href);
  }

  const overviewItems: OverviewListItem[] = (data?.overview_rows ?? []).map(row => ({
    label: row.name,
    sub: row.context_label,
    chip: row.status_label,
    chipTone: CHIP_TONE[row.status_kind],
    onOpen: () => onOpenChart(row.id),
  }));

  return (
    <div>
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Organization</div>
      <div className="pagehead">
        <div>
          <h1>Organization <em>structure</em></h1>
          <p className="lede" style={{ maxWidth: 560 }}>
            Manage legal entities, business units, departments, positions and reporting relationships.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => onOpenChart()}>
          <i className="ti ti-plus" /> Add org unit
        </button>
      </div>

      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> <div>{error}</div>
        </div>
      )}

      <div className="stats">
        <StatCard label="LEGAL ENTITIES" value={data?.legal_entities.count ?? "—"} sub="India operations" tone="brand" />
        <StatCard label="ORG UNITS" value={data?.org_units.count ?? "—"} sub="All active" tone="ok" />
        <StatCard
          label="DEPARTMENTS"
          value={data?.departments.count ?? "—"}
          sub={data ? `Across ${data.departments.locations_count} location${data.departments.locations_count === 1 ? "" : "s"}` : ""}
          tone="warn"
        />
        <StatCard
          label="OPEN POSITIONS"
          value={data?.open_positions.count ?? "—"}
          sub={data ? `${data.open_positions.manager_vacancy_count} high priority` : ""}
          tone="crit"
        />
      </div>

      <div className="module-grid">
        <OverviewList
          title="Organization overview"
          items={overviewItems}
          emptyIcon="ti-sitemap"
          emptyTitle="No org units yet"
        />

        <QuickActionsGrid
          items={[
            { title: "Organization chart", sub: "View reporting hierarchy", onClick: () => onOpenChart() },
            { title: "Positions & bands", sub: "Manage grades and job families", onClick: () => onOpenChart() },
            { title: "Cost centers", sub: "Map payroll and finance codes", onClick: () => onOpenChart() },
            {
              title: "Locations",
              sub: data && data.locations.length > 0 ? data.locations.join(" · ") : "No active branches yet",
              onClick: () => router.push("/dashboard/branches"),
            },
          ]}
          chartData={(data?.headcount_by_unit ?? []).map(d => ({ label: d.name.length > 6 ? `${d.name.slice(0, 5)}…` : d.name, count: d.headcount }))}
        />
      </div>

      <BrandBanner />
      <CapabilityGrid title="Complete capability coverage" sub="Lifecycle functions designed for multi-year HR operations." items={CAPABILITIES} onOpen={go} />
      <OperationalToolsGrid title="Operational tools" sub="Role-aware tools with effective dates, approval states and audit events." items={OPERATIONAL_TOOLS} onLaunch={go} />
      <PlatformSafeguards />
    </div>
  );
}
