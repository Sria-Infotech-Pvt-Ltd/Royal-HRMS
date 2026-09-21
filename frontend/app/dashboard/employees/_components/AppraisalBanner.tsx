"use client";

// Small card surfacing the active performance-review cycle on the Employee
// Directory — the one Performance touch-point the screenshot showed
// embedded here. Fetches its own tiny summary endpoint (banner-summary/)
// rather than the full HR queue, and renders nothing at all for anyone
// without performance.manage_cycles or when there's no active cycle.

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";

interface BannerSummary {
  cycle_name: string;
  total: number;
  self_reviews_done: number;
  latest_employee_name: string | null;
  latest_employee_code: string | null;
  latest_status_display: string | null;
}

export default function AppraisalBanner() {
  const canManage = usePermission("performance.manage_cycles");
  const { data } = useFetch<BannerSummary>(canManage ? API.performance.bannerSummary : null);
  const router = useRouter();

  if (!canManage || !data || !data.cycle_name) return null;

  const remaining = data.total - data.self_reviews_done;
  const summary = data.latest_employee_name
    ? `${data.latest_employee_name}${data.latest_employee_code ? ` · ${data.latest_employee_code}` : ""} · ${data.latest_status_display} · ${remaining > 0 ? `${remaining} other employee review${remaining === 1 ? "" : "s"} still pending` : "All self-reviews submitted"}.`
    : "No employee reviews started yet.";

  return (
    <div className="card mb-6" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, padding: "16px 22px", flexWrap: "wrap" }}>
      <div>
        <div style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)" }}>
          {data.cycle_name} appraisal · HR review queue
        </div>
        <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>{summary}</div>
      </div>
      <button className="btn btn-ghost btn-sm" onClick={() => router.push("/dashboard/performance")}>
        Open employee review
      </button>
    </div>
  );
}
