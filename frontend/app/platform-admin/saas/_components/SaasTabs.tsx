"use client";

// Sub-navigation for Platform Admin → SaaS & Subscriptions.

import { useEffect, useId, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { formatMoney } from "@/lib/currency";
import type { PaymentMethod, PaymentStatus, SubscriptionProvisioning } from "@/types/platformAdmin";

const TABS = [
  { href: "/platform-admin/saas", label: "Dashboard", icon: "ti-layout-dashboard",
    help: "Overview of subscription plans, customers, active subscriptions and registration activity." },
  { href: "/platform-admin/saas/plans", label: "Subscription Plans", icon: "ti-stack-2",
    help: "Create and manage plans: pricing, billing periods, employee limits and the HRMS modules included." },
  { href: "/platform-admin/saas/subscriptions", label: "Customer Subscriptions", icon: "ti-building-store",
    help: "See each company's plan and modules, assign plans, record payments and manage subscriptions." },
  { href: "/platform-admin/saas/registrations", label: "Customer Registrations", icon: "ti-user-plus",
    help: "Review website sign-ups, check their payment status and approve or reject them." },
  { href: "/platform-admin/saas/history", label: "Subscription History", icon: "ti-history",
    help: "Past subscription changes: plan assignments, plan changes, payments and other activity." },
];

// ⓘ next to a tab: hover / keyboard focus on desktop, tap on touch screens.
// A separate button (not inside the tab link) so it never triggers navigation.
function TabInfo({ label, text }: { label: string; text: string }) {
  const [open, setOpen] = useState(false);
  const [align, setAlign] = useState<"left" | "center" | "right">("center");
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, [open]);

  function show() {
    const r = ref.current?.getBoundingClientRect();
    const visible = window.visualViewport?.width ?? window.innerWidth;   // what's on screen, not the layout width
    if (r) setAlign(r.left < 130 ? "left" : visible - r.right < 130 ? "right" : "center");
    setOpen(true);
  }

  const pos = align === "left" ? { left: -6 } : align === "right" ? { right: -6 } : { left: "50%", transform: "translateX(-50%)" };
  return (
    <span ref={ref} style={{ position: "relative", display: "inline-flex" }}
      onMouseEnter={show} onMouseLeave={() => setOpen(false)}>
      <button type="button" aria-label={`About ${label}`} aria-expanded={open} aria-describedby={open ? id : undefined}
        onClick={show} onFocus={show} onBlur={() => setOpen(false)}
        style={{ display: "inline-flex", padding: 2, border: 0, background: "none", cursor: "help", borderRadius: 4,
          color: "var(--on-variant)", fontSize: 14, lineHeight: 1 }}>
        <i className="ti ti-info-circle" />
      </button>
      {open && (
        <span role="tooltip" id={id} style={{
          position: "absolute", top: "calc(100% + 6px)", zIndex: 20, width: "max-content", maxWidth: "min(240px, 80vw)",
          background: "var(--on-bg)", color: "var(--surface)", fontSize: 12, fontWeight: 400, lineHeight: 1.45,
          padding: "7px 10px", borderRadius: 6, boxShadow: "0 4px 12px rgba(0,0,0,.18)", whiteSpace: "normal", ...pos,
        }}>{text}</span>
      )}
    </span>
  );
}

export function apiMessage(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback;
}

export const fmtMoney = (amount: string | number, currency = "INR") => formatMoney(amount, currency);

export const fmtDate = (d: string | null) =>
  d ? new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const EVENT_LABEL: Record<string, string> = {
  assigned: "Assigned", plan_changed: "Plan changed", extended: "Period changed", activated: "Activated",
  deactivated: "Deactivated", provisioning_retried: "Provisioning retried",
  payment_recorded: "Payment recorded", payment_verified: "Payment confirmed", payment_rejected: "Payment rejected",
  payment_waived: "Payment waived", payment_waiver_removed: "Waiver removed", amount_due_changed: "Amount due changed",
  provisioned: "Provisioned", provisioning_failed: "Provisioning failed", edited: "Subscription edited",
};

// "Starter → Growth" for plan changes; just the plan for events with no "before" (payments etc.).
export function planChange(h: { before: Record<string, unknown>; after: Record<string, unknown> }): string {
  const after = String(h.after.plan_name ?? "—");
  return h.before.plan_name && h.before.plan_name !== h.after.plan_name ? `${String(h.before.plan_name)} → ${after}` : after;
}

type Badge = { label: string; cls: string };

export const PAYMENT_BADGE: Record<PaymentStatus, Badge> = {
  pending: { label: "Pending", cls: "badge-warn" },
  paid: { label: "Paid", cls: "badge-success" },
  partially_paid: { label: "Partially paid", cls: "badge-info" },
  failed: { label: "Failed", cls: "badge-error" },
  waived: { label: "Waived", cls: "badge-neutral" },
};

export const PROVISION_BADGE: Record<SubscriptionProvisioning, Badge> = {
  awaiting_payment: { label: "Awaiting payment", cls: "badge-warn" },
  pending: { label: "In progress", cls: "badge-neutral" },
  success: { label: "Success", cls: "badge-success" },
  failed: { label: "Failed", cls: "badge-error" },
};

export const PAYMENT_METHODS: [PaymentMethod, string][] = [
  ["upi", "UPI"], ["bank_transfer", "Bank transfer"], ["neft", "NEFT"], ["rtgs", "RTGS"],
  ["cash", "Cash"], ["cheque", "Cheque"], ["other", "Other"],
];

// Plan price × employees for one billing period, plus GST when it is extra.
export default function SaasTabs({ title, sub, actions }: { title: string; sub: string; actions?: React.ReactNode }) {
  const pathname = usePathname();
  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{title}</div>
          <div className="page-sub">{sub}</div>
        </div>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 18, padding: 4, borderRadius: 12,
        background: "var(--bg-mid)", width: "fit-content" }}>
        {TABS.map(t => {
          const active = t.href === "/platform-admin/saas" ? pathname === t.href : pathname.startsWith(t.href);
          return (
            <span key={t.href} style={{ display: "flex", alignItems: "center", borderRadius: 8, paddingRight: 8,
              background: active ? "var(--surface)" : "transparent" }}>
              <a href={t.href} aria-current={active ? "page" : undefined} style={{
                display: "flex", alignItems: "center", gap: 6, padding: "7px 4px 7px 14px", fontSize: 13,
                fontWeight: active ? 600 : 500, textDecoration: "none",
                color: active ? "var(--primary)" : "var(--on-variant)",
              }}>
                <i className={`ti ${t.icon}`} /> {t.label}
              </a>
              <TabInfo label={t.label} text={t.help} />
            </span>
          );
        })}
      </div>
    </>
  );
}
