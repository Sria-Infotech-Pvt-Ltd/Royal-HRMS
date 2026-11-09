import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ApprovalChain } from "@/types/approvers";

interface HookState { chain: ApprovalChain | null; loading: boolean; error: string | null }
let hookState: HookState;
vi.mock("@/hooks/useMyApprovals", () => ({ useMyApprovals: () => hookState }));

import ReportingApprovalsCard, { ReportingApprovalsView } from "./ReportingApprovalsCard";

const manager = { full_name: "Vikram Rao", role: "Delivery Manager", source: "assigned" };
const hr = { full_name: "Asha Menon", role: "HR Business Partner" };

const chain = (overrides: Partial<ApprovalChain> = {}): ApprovalChain => ({
  workflow: "leave", reporting_manager: manager, warnings: [], blocking: [], can_submit: true,
  stages: [
    { stage: "l1", label: "L1 approver", status: "assigned", user: { full_name: "Vikram Rao", role: "Delivery Manager" }, note: "" },
    { stage: "l2", label: "L2 HR approver", status: "assigned", user: hr, note: "" },
  ],
  ...overrides,
});

describe("ReportingApprovalsView", () => {
  it("shows the reporting manager, L1 and L2 with their names and roles", () => {
    const html = renderToStaticMarkup(<ReportingApprovalsView chain={chain()} />);
    expect(html).toContain("Reporting manager");
    expect(html).toContain("Vikram Rao — Delivery Manager");
    expect(html).toContain("L2 HR approver");
    expect(html).toContain("Asha Menon — HR Business Partner");
    expect(html).not.toContain("Not assigned");
  });

  it("says Not assigned for anything missing", () => {
    const html = renderToStaticMarkup(<ReportingApprovalsView chain={chain({
      reporting_manager: null,
      stages: [
        { stage: "l1", label: "L1 approver", status: "missing", user: null, note: "Nobody is assigned." },
        { stage: "l2", label: "L2 HR approver", status: "missing", user: null, note: "Nobody is assigned." },
      ],
    })} />);
    expect(html.match(/Not assigned/g)).toHaveLength(3);
  });

  it("explains that a manager's leave skips L1", () => {
    const html = renderToStaticMarkup(<ReportingApprovalsView chain={chain({
      stages: [
        { stage: "l1", label: "L1 approver", status: "skipped", user: null, note: "Managers' leave goes straight to HR." },
        { stage: "l2", label: "L2 HR approver", status: "assigned", user: hr, note: "" },
      ],
    })} />);
    expect(html).toContain("Not needed");
  });

  it("lists the warnings the server sent", () => {
    const html = renderToStaticMarkup(<ReportingApprovalsView chain={chain({ warnings: ["L1 approver: The assigned l1 approver (Old Boss) is inactive."] })} />);
    expect(html).toContain("is inactive");
  });

  it("has no edit control: it is read-only", () => {
    const html = renderToStaticMarkup(<ReportingApprovalsView chain={chain()} />);
    expect(html).not.toMatch(/<button|<select|<input/);
  });
});

describe("ReportingApprovalsCard", () => {
  beforeEach(() => { hookState = { chain: chain(), loading: false, error: null }; });

  it("has the title the requirement names", () => {
    expect(renderToStaticMarkup(<ReportingApprovalsCard />)).toContain("YOUR REPORTING &amp; APPROVALS");
  });

  it("says so while loading and when the answer cannot be loaded", () => {
    hookState = { chain: null, loading: true, error: null };
    expect(renderToStaticMarkup(<ReportingApprovalsCard />)).toContain("Loading");
    hookState = { chain: null, loading: false, error: "Request failed." };
    expect(renderToStaticMarkup(<ReportingApprovalsCard />)).toContain("Could not load your approvers");
  });
});
