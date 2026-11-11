import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { LeaveRequest } from "@/app/dashboard/leave/_data";

// Server-render (no DOM) like the other component tests in this repo; useFetch
// is mocked per URL so each component renders its loaded state.
const fetched: Record<string, unknown> = {};
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    const key = url ? Object.keys(fetched).find(k => url.startsWith(k)) : undefined;
    return { data: key ? fetched[key] : null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));
vi.mock("@/lib/clientApi", () => ({ default: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn() } }));

import EscalationSettingsCard from "@/app/dashboard/settings/approval-rules/_components/EscalationSettingsCard";
import DelegationsSection from "./DelegationsSection";
import LeaveCancellationsSection from "./LeaveCancellationsSection";
import LeaveCancellationPanel from "@/app/dashboard/leave/_components/LeaveCancellationPanel";

const person = (id: string, name: string) => ({ id, name, employee_id: id.toUpperCase(), branch: "North" });

const leave = (over: Partial<LeaveRequest> = {}): LeaveRequest => ({
  id: "lr1", leave_type: "casual", leave_type_display: "Casual Leave", duration: "full_day",
  duration_display: "Full Day", start_date: "2026-12-07", end_date: "2026-12-07", total_days: 1, lop_days: 0,
  reason: "Trip", status: "approved", is_lwp: false, employee_name: "Asha", employee_code: "E1",
  employee_dept: "", employee_branch: "North", l1_approver_name: "Mgr", l1_status: "approved", l1_remarks: "",
  l1_actioned_at: null, l2_approver_name: "", l2_status: null, l2_remarks: "", l2_actioned_at: null,
  contact_during_leave: "", handover_to: "", handover_notes: "", document_url: null, created_at: "2026-11-01",
  approved_by: "Mgr", approved_at: null, ...over,
} as LeaveRequest);

beforeEach(() => {
  for (const k of Object.keys(fetched)) delete fetched[k];
});

describe("EscalationSettingsCard", () => {
  const settings = {
    is_enabled: true, reminder_after_days: 1, first_escalation_after_days: 2, second_escalation_after_days: 3,
    escalation_head: person("h1", "HR Head"), applies_to_leave: true, applies_to_attendance: true, can_edit: true,
  };

  it("shows the saved timeline and the head", () => {
    fetched["/approvals/escalation-settings/head-candidates/"] = [person("h1", "HR Head")];
    fetched["/approvals/escalation-settings/"] = settings;
    const html = renderToStaticMarkup(<EscalationSettingsCard />);
    expect(html).toContain("Automatic Reminders");
    expect(html).toContain("Day 1:");
    expect(html).toContain("Day 2:");
    expect(html).toContain("Day 5:");
    expect(html).toContain("Escalated to HR Head");
    expect(html).toContain("Save Escalation Settings");
  });

  it("is read-only without settings.edit", () => {
    fetched["/approvals/escalation-settings/"] = { ...settings, can_edit: false };
    const html = renderToStaticMarkup(<EscalationSettingsCard />);
    expect(html).not.toContain("Save Escalation Settings");
    expect(html).toContain("disabled");
  });
});

describe("DelegationsSection", () => {
  it("splits delegations I gave from ones I received", () => {
    const base = { start_date: "2020-01-01", end_date: "2099-01-01", workflows: ["leave"], reason: "", active: true,
                   revoked: false, revoked_at: null, created_at: "" };
    fetched["/approvals/delegations/eligible/"] = [person("u2", "Ravi")];
    fetched["/approvals/delegations/"] = [
      { ...base, id: "d1", delegator: person("me", "Me"), delegate: person("u2", "Ravi"), can_revoke: true,
        given: true, received: false },
      { ...base, id: "d2", delegator: person("u3", "Kiran"), delegate: person("me", "Me"), can_revoke: false,
        given: false, received: true, workflows: ["attendance"] },
    ];
    const html = renderToStaticMarkup(<DelegationsSection />);
    const [mine, theirs] = html.split("Delegated to me");
    expect(mine).toContain("Ravi");
    expect(mine).toContain("Revoke");
    expect(theirs).toContain("Kiran");
    expect(theirs).toContain("Attendance");
    expect(theirs).not.toContain("Revoke");
    expect(html).toContain("Active");
  });

  it("shows empty states", () => {
    fetched["/approvals/delegations/"] = [];
    const html = renderToStaticMarkup(<DelegationsSection />);
    expect(html).toContain("You haven&#x27;t delegated your approvals.");
    expect(html).toContain("No one has delegated approvals to you.");
  });
});

describe("LeaveCancellationsSection", () => {
  it("lists waiting requests with their reason and actions", () => {
    fetched["/leave/cancellations/"] = [leave({ cancellation_status: "requested", cancellation_reason: "Plans changed" })];
    const html = renderToStaticMarkup(<LeaveCancellationsSection />);
    expect(html).toContain("Asha");
    expect(html).toContain("Plans changed");
    expect(html).toContain("Approve cancellation");
  });

  it("shows an empty state", () => {
    fetched["/leave/cancellations/"] = [];
    expect(renderToStaticMarkup(<LeaveCancellationsSection />)).toContain("No cancellation requests waiting for you.");
  });
});

describe("LeaveCancellationPanel", () => {
  const render = (r: LeaveRequest) => renderToStaticMarkup(<LeaveCancellationPanel request={r} onChanged={() => {}} />);

  it("renders nothing when there is nothing to show", () => {
    expect(render(leave({ status: "pending" }))).toBe("");
  });

  it("offers the employee a cancellation request", () => {
    const html = render(leave({ can_request_cancellation: true }));
    expect(html).toContain("Request cancellation");
    expect(html).not.toContain("Approve cancellation");
  });

  it("offers the approver a decision and shows the reason", () => {
    const html = render(leave({ cancellation_status: "requested", cancellation_reason: "Plans changed",
                                can_decide_cancellation: true }));
    expect(html).toContain("Cancellation pending");
    expect(html).toContain("Plans changed");
    expect(html).toContain("Approve cancellation");
    expect(html).toContain("Reject cancellation");
  });

  it("shows a rejection with its note and lets the employee ask again", () => {
    const html = render(leave({ cancellation_status: "rejected", cancellation_remarks: "Peak season",
                                can_request_cancellation: true }));
    expect(html).toContain("Cancellation rejected");
    expect(html).toContain("Peak season");
    expect(html).toContain("Request cancellation");
  });
});
