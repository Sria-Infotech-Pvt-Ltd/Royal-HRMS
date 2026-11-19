import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// Opening Team Approvals from a link (a dashboard chart bar) must show only the asked-for type, status and month.
function leave(id: string, name: string, status: string, createdAt: string) {
  return {
    id, employee_name: name, employee_code: id, employee_dept: "Ops", employee_branch: "Hyderabad", status, created_at: createdAt,
    leave_type: "casual", leave_type_display: "Casual Leave", start_date: "2026-11-10", end_date: "2026-11-10", total_days: 1,
  };
}

const LEAVES = [
  leave("L1", "Rejected November Person", "rejected", "2026-11-05T09:00:00"),
  leave("L2", "Approved November Person", "approved", "2026-11-06T09:00:00"),
  leave("L3", "Rejected October Person", "rejected", "2026-10-05T09:00:00"),
  leave("L4", "Pending November Person", "pending", "2026-11-07T09:00:00"),
];

vi.mock("@/hooks/usePermission", () => ({ usePermission: () => true }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => ({
    data: url?.startsWith("/leave/") || url?.includes("leave") ? { results: LEAVES } : null,
    loading: false, error: null, status: null, refetch: () => {},
  }),
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: () => {} }) }));
vi.mock("@/components/DialogProvider", () => ({ confirmDialog: async () => false }));

import TeamApprovalsSection from "./TeamApprovalsSection";

describe("TeamApprovalsSection opened from a link", () => {
  it("shows only the rejected requests of that month", () => {
    const html = renderToStaticMarkup(
      <TeamApprovalsSection initialFilters={{ type: "leave", status: "rejected", dateFrom: "2026-11-01", dateTo: "2026-11-30" }} />,
    );
    expect(html).toContain("Rejected November Person");
    expect(html).not.toContain("Approved November Person");
    expect(html).not.toContain("Rejected October Person");
    expect(html).not.toContain("Pending November Person");
  });

  it("without a link it still opens on the pending requests", () => {
    const html = renderToStaticMarkup(<TeamApprovalsSection />);
    expect(html).toContain("Pending November Person");
    expect(html).not.toContain("Rejected November Person");
  });
});
