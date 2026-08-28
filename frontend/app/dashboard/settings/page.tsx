"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const SETTINGS_ITEMS = [
  { id: "company",            cat: "company", icon: "ti-building",        iconClass: "sc-company", label: "Company Info",          desc: "Name, GST, address, registration details" },
  { id: "permissions",        cat: "company", icon: "ti-shield-lock",     iconClass: "sc-company", label: "Roles & Permissions",   desc: "Role-based access control for all users" },
  { id: "leave-policy",       cat: "modules", icon: "ti-beach",           iconClass: "sc-modules", label: "Leave Policy",          desc: "Configure leave types, accruals and limits" },
  { id: "approval-rules",     cat: "modules", icon: "ti-sitemap",         iconClass: "sc-modules", label: "Approval Rules",        desc: "Who approves leave, expenses, resignation and loans" },
  { id: "holiday-calendar",   cat: "modules", icon: "ti-calendar-event",  iconClass: "sc-modules", label: "Holiday Calendar",      desc: "Manage national, regional and company holidays" },
  { id: "payroll-config",     cat: "modules", icon: "ti-report-money",    iconClass: "sc-modules", label: "Payroll Rules",         desc: "Salary components, tax slabs and statutory" },
  { id: "attendance-config",  cat: "modules", icon: "ti-clock",           iconClass: "sc-modules", label: "Attendance Rules",      desc: "Shift timings, late marks and overtime" },
  { id: "assessment-config",  cat: "modules", icon: "ti-clipboard-check", iconClass: "sc-modules", label: "Assessment Config",     desc: "Pass percentage, attempt limits and time settings" },
  { id: "onboarding-fields",  cat: "modules", icon: "ti-forms",           iconClass: "sc-modules", label: "Onboarding Fields",     desc: "Show, hide, require, or add fields on the employee onboarding wizard" },
  { id: "referral-rules",     cat: "modules", icon: "ti-user-plus",       iconClass: "sc-modules", label: "Referral Rules",        desc: "Manage the rules and bonus details shown on the Referral page" },
  { id: "email-templates",    cat: "comm",    icon: "ti-mail",            iconClass: "sc-comm",    label: "Email Templates",       desc: "Customize transactional emails and birthday wish settings" },
  { id: "smtp",               cat: "comm",    icon: "ti-server",          iconClass: "sc-comm",    label: "SMTP Settings",         desc: "Outgoing email server configuration" },
  { id: "notifications",      cat: "comm",    icon: "ti-bell",            iconClass: "sc-comm",    label: "Notifications",         desc: "In-app and email notification preferences" },
  { id: "employee-code",      cat: "company", icon: "ti-id-badge",        iconClass: "sc-company", label: "Employee ID Format",    desc: "Prefix, padding, and starting number for employee codes" },
  { id: "audit",              cat: "system",  icon: "ti-history",         iconClass: "sc-system",  label: "Audit Log",             desc: "View all system actions and changes" },
] as const;

const CATS = [
  { id: "all",     icon: "ti-grid-dots", label: "All Settings" },
  { id: "company", icon: "ti-building",  label: "Company" },
  { id: "modules", icon: "ti-stack-2",   label: "Modules" },
  { id: "comm",    icon: "ti-mail",      label: "Communication" },
  { id: "system",  icon: "ti-server",    label: "System" },
] as const;

type CatId = "all" | "company" | "modules" | "comm" | "system";

const ITEM_ROUTES: Record<string, string> = {
  company:                "/dashboard/settings/company",
  permissions:            "/dashboard/settings/permissions",
  smtp:                   "/dashboard/settings/smtp",
  "email-templates":      "/dashboard/settings/email-templates",
  audit:                  "/dashboard/settings/audit",
  "employee-code":        "/dashboard/settings/employee-code",
  "leave-policy":         "/dashboard/settings/leave-policy",
  "holiday-calendar":     "/dashboard/settings/holiday-calendar",
  "approval-rules":       "/dashboard/settings/approval-rules",
  "attendance-config":    "/dashboard/settings/attendance-config",
  "payroll-config":       "/dashboard/settings/payroll-config",
  "assessment-config":    "/dashboard/settings/assessment-config",
  "onboarding-fields":    "/dashboard/settings/onboarding-fields",
  "referral-rules":       "/dashboard/settings/referral-rules",
  "notifications":        "/dashboard/settings/notifications",
};

const COMING_SOON_ITEMS = new Set<string>([]);

export default function SettingsPage() {
  const router = useRouter();
  const [activeCat, setActiveCat] = useState<CatId>("all");

  const visible = activeCat === "all"
    ? SETTINGS_ITEMS
    : SETTINGS_ITEMS.filter((i) => i.cat === activeCat);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Settings</div>
          <div className="page-sub">Configure all Aira HRMS modules from one place</div>
        </div>
      </div>

      {/* Category pills */}
      <div className="settings-cats">
        {CATS.map((c) => (
          <button
            key={c.id}
            className={`settings-cat-pill${activeCat === c.id ? " active" : ""}`}
            onClick={() => setActiveCat(c.id)}
          >
            <i className={`ti ${c.icon}`} /> {c.label}
          </button>
        ))}
      </div>

      {/* Settings card grid */}
      <div className="settings-cards-grid">
        {visible.map((item) => {
          const isSoon = COMING_SOON_ITEMS.has(item.id);
          return (
            <div
              key={item.id}
              className="settings-card-tile"
              style={{ cursor: isSoon ? "default" : "pointer", opacity: isSoon ? 0.7 : 1 }}
              onClick={() => {
                const route = ITEM_ROUTES[item.id];
                if (route) router.push(route);
              }}
            >
              <div className={`settings-card-icon ${item.iconClass}`}>
                <i className={`ti ${item.icon}`} />
              </div>
              <div className="settings-card-body">
                <div className="settings-card-name" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {item.label}
                  {isSoon && (
                    <span style={{ fontSize: 9, fontWeight: 700, background: "var(--outline-v)", color: "var(--outline)", padding: "1px 6px", borderRadius: 4, letterSpacing: "0.04em" }}>
                      SOON
                    </span>
                  )}
                </div>
                <div className="settings-card-desc">{item.desc}</div>
              </div>
              {!isSoon && (
                <i className="ti ti-chevron-right" style={{ fontSize: 16, color: "var(--outline)", marginLeft: "auto", alignSelf: "center" }} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
