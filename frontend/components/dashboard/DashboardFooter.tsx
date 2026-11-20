"use client";

// Global footer, present on every dashboard page — matches the reference
// mockup's footer exactly (verbatim markup from public/reference.html):
// brand mini-logo + name/subtitle on the left, footer-nav buttons in the
// middle, static demo/copyright text on the right.

import { useRouter } from "next/navigation";

// "Interactive demo" is only true of a demo build; set NEXT_PUBLIC_DEMO_BUILD=true for one. UAT and production show nothing.
const IS_DEMO_BUILD = process.env.NEXT_PUBLIC_DEMO_BUILD === "true";

export default function DashboardFooter() {
  const router = useRouter();

  return (
    <footer className="site-footer">
      <div className="footer-inner">
        <div className="footer-brand">
          {/* The same AIRA mark as the top-left of the app: the product's logo, not the company's. */}
          <span className="footer-logo" aria-hidden="true">
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
              <path d="M12 3 21 8v8l-9 5-9-5V8z" />
            </svg>
          </span>
          <span>
            <b>AIRA HR Operations</b>
            <small>Artificial Intelligence Resources Assistance</small>
          </span>
        </div>

        <div className="footer-links" aria-label="Footer navigation">
          <button type="button" onClick={() => router.push("/dashboard/privacy")}>Privacy &amp; retention</button>
          <button type="button" onClick={() => router.push("/dashboard/security")}>Security</button>
          <button type="button" onClick={() => router.push("/dashboard/settings/audit")}>Audit trail</button>
          <button type="button" onClick={() => router.push("/dashboard/ess?tab=hrHelp")}>Support</button>
        </div>

        <div className="footer-meta">{IS_DEMO_BUILD ? "Interactive demo · " : ""}Role-aware access · © 2026 AIRA</div>
      </div>
    </footer>
  );
}
