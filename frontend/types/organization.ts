// Shapes backing the Organization Structure landing page (Screen 3). Every
// field is a real number/row computed by the org-structure overview view —
// never a fabricated demo value.

export type OrgOverviewRowStatusKind = "manager_vacancy" | "open_positions" | "headcount";

export interface OrgOverviewRow {
  id: string;
  name: string;
  context_label: string;
  status_kind: OrgOverviewRowStatusKind;
  status_label: string;
}

export interface OrgHeadcountByUnit {
  name: string;
  headcount: number;
}

export interface OrganizationOverview {
  legal_entities: { count: number };
  org_units: { count: number };
  departments: { count: number; locations_count: number };
  open_positions: { count: number; manager_vacancy_count: number };
  locations: string[];
  overview_rows: OrgOverviewRow[];
  headcount_by_unit: OrgHeadcountByUnit[];
}
