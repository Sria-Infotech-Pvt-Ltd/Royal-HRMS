"use client";

import { useRouter } from "next/navigation";

interface PortalOption {
  key: "hr" | "employee";
  icon: string;
  accent: string;
  title: string;
  description: string;
  cta: string;
}

const OPTIONS: PortalOption[] = [
  {
    key: "hr",
    icon: "ti-shield-check",
    accent: "#1e4e8c",
    title: "HR & Admin Login",
    description: "Manage employees, payroll, attendance, and company settings.",
    cta: "Access HR Portal",
  },
  {
    key: "employee",
    icon: "ti-user-circle",
    accent: "#7c3aed",
    title: "Employee Login",
    description: "View your payslips, apply for leave, and track your attendance.",
    cta: "Access Employee Portal",
  },
];

export default function PortalChooserPage() {
  const router = useRouter();

  return (
    <div className="portal-root">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/login.jpg" alt="" aria-hidden="true" className="portal-backdrop" />
      <div className="portal-backdrop-tint" />

      <div className="portal-nav">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/logo.png" alt="Royal HRMS" className="portal-brand-logo" />
        <span className="portal-brand-name">Royal HRMS</span>
      </div>

      <h1 className="portal-heading">Welcome to Royal HRMS</h1>
      <p className="portal-subheading">Choose how you&apos;d like to sign in</p>

      <div className="portal-cards">
        {OPTIONS.map(opt => (
          <button
            key={opt.key}
            type="button"
            className="portal-card"
            style={{ "--portal-accent": opt.accent } as React.CSSProperties}
            onClick={() => router.push(`/login?portal=${opt.key}`)}
          >
            <span className="portal-card-icon">
              <i className={`ti ${opt.icon}`} />
            </span>
            <span className="portal-card-title">{opt.title}</span>
            <span className="portal-card-desc">{opt.description}</span>
            <span className="portal-card-cta">
              {opt.cta} <i className="ti ti-arrow-right" />
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
