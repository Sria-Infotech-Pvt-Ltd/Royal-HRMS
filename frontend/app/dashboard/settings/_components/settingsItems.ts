// What the Settings landing page lists: the setting groups, their categories and where each one goes.

export type CatId = "all" | "company" | "modules" | "comm" | "system";
export type ItemCat = Exclude<CatId, "all">;

export interface SettingsItem { id: string; cat: ItemCat; icon: string; label: string; desc: string; route: string }

export const CATEGORY_INFO: Record<ItemCat, { label: string; icon: string; colour: string; blurb: string }> = {
  company: { label: "Company", icon: "ti-building", colour: "var(--brand)", blurb: "Who you are and who can do what" },
  modules: { label: "Modules", icon: "ti-stack-2",  colour: "var(--brand)", blurb: "Rules for leave, payroll, attendance and more" },
  comm:    { label: "Communication", icon: "ti-mail", colour: "var(--brand)", blurb: "Emails and notifications" },
  system:  { label: "System", icon: "ti-server",    colour: "var(--brand)", blurb: "Syncs and the audit trail" },
};

export const CATEGORY_ORDER: ItemCat[] = ["company", "modules", "comm", "system"];

const BASE = "/dashboard/settings";
export const SETTINGS_ITEMS: SettingsItem[] = [
  { id: "company",           cat: "company", icon: "ti-building",        label: "Company Info",           desc: "Name, GST, address, registration details",                              route: `${BASE}/company` },
  { id: "access",            cat: "company", icon: "ti-key",             label: "Permissions",            desc: "What everyone can do, what each position can do, and extra permissions for one person", route: `${BASE}/access` },
  { id: "leave-policy",      cat: "modules", icon: "ti-beach",           label: "Leave Policy",           desc: "Configure leave types, accruals and limits",                            route: `${BASE}/leave-policy` },
  { id: "approval-rules",    cat: "modules", icon: "ti-sitemap",         label: "Approval Rules",         desc: "Who approves leave, expenses, resignation and loans",                   route: `${BASE}/approval-rules` },
  { id: "holiday-calendar",  cat: "modules", icon: "ti-calendar-event",  label: "Holiday Calendar",       desc: "Manage national, regional and company holidays",                        route: `${BASE}/holiday-calendar` },
  { id: "payroll-config",    cat: "modules", icon: "ti-report-money",    label: "Payroll Rules",          desc: "Salary components, tax slabs and statutory",                            route: `${BASE}/payroll-config` },
  { id: "attendance-config", cat: "modules", icon: "ti-clock",           label: "Attendance Rules",       desc: "Shift timings, late marks and overtime",                                route: `${BASE}/attendance-config` },
  { id: "assessment-config", cat: "modules", icon: "ti-clipboard-check", label: "Assessment Config",      desc: "Pass percentage, attempt limits and time settings",                     route: `${BASE}/assessment-config` },
  { id: "onboarding-fields", cat: "modules", icon: "ti-forms",           label: "Onboarding Fields",      desc: "Show, hide, require, or add fields on the employee onboarding wizard",  route: `${BASE}/onboarding-fields` },
  { id: "referral-rules",    cat: "modules", icon: "ti-user-plus",       label: "Referral Rules",         desc: "Manage the rules and bonus details shown on the Referral page",         route: `${BASE}/referral-rules` },
  { id: "email-templates",   cat: "comm",    icon: "ti-mail",            label: "Email Templates",        desc: "Customize transactional emails and birthday wish settings",             route: `${BASE}/email-templates` },
  { id: "smtp",              cat: "comm",    icon: "ti-server",          label: "SMTP Settings",          desc: "Outgoing email server configuration",                                   route: `${BASE}/smtp` },
  { id: "notifications",     cat: "comm",    icon: "ti-bell",            label: "Notifications",          desc: "In-app and email notification preferences",                             route: `${BASE}/notifications` },
  { id: "employee-code",     cat: "company", icon: "ti-id-badge",        label: "Employee ID Format",     desc: "Prefix, padding, and starting number for employee codes",               route: `${BASE}/employee-code` },
  { id: "audit",             cat: "system",  icon: "ti-history",         label: "Audit Log",              desc: "View all system actions and changes",                                   route: `${BASE}/audit` },
];

/** The settings matching every typed word (in the name or the description) within the chosen category. */
export function filterSettings(items: SettingsItem[], search: string, cat: CatId): SettingsItem[] {
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  return items.filter(item => (cat === "all" || item.cat === cat) && words.every(word => `${item.label} ${item.desc}`.toLowerCase().includes(word)));
}

export function countByCategory(items: SettingsItem[], search: string): Record<CatId, number> {
  const counts = { all: 0, company: 0, modules: 0, comm: 0, system: 0 } as Record<CatId, number>;
  for (const item of filterSettings(items, search, "all")) { counts.all += 1; counts[item.cat] += 1; }
  return counts;
}
