import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import type { ApprovalChain } from "@/types/approvers";
import ApprovalChainPreview, { chainBlocksSubmit } from "./ApprovalChainPreview";

const asha = { full_name: "Asha Menon", role: "HR Business Partner" };

const chain = (overrides: Partial<ApprovalChain> = {}): ApprovalChain => ({
  workflow: "leave", reporting_manager: null, warnings: [], blocking: [], can_submit: true,
  stages: [
    { stage: "l1", label: "L1 approver", status: "assigned", user: { full_name: "Vikram Rao", role: "Delivery Manager" }, note: "" },
    { stage: "l2", label: "L2 HR approver", status: "assigned", user: asha, note: "" },
  ],
  ...overrides,
});

const render = (value: ApprovalChain) =>
  renderToStaticMarkup(<ApprovalChainPreview chain={value} acknowledged={false} onAcknowledge={() => {}} />);

describe("chainBlocksSubmit", () => {
  it("lets a complete chain through", () => {
    expect(chainBlocksSubmit(chain(), false)).toBe(false);
  });

  it("blocks a chain that cannot finish, even if the person ticks the box", () => {
    const broken = chain({ can_submit: false, blocking: ["Nobody is available to approve this request."] });
    expect(chainBlocksSubmit(broken, true)).toBe(true);
  });

  it("holds a chain with gaps until the person acknowledges it", () => {
    const gappy = chain({ warnings: ["L1 approver: Nobody is assigned."] });
    expect(chainBlocksSubmit(gappy, false)).toBe(true);
    expect(chainBlocksSubmit(gappy, true)).toBe(false);
  });

  it("does not block when the chain could not be loaded (the server still refuses a broken one)", () => {
    expect(chainBlocksSubmit(null, false)).toBe(false);
  });
});

describe("ApprovalChainPreview", () => {
  it("shows who approves at each stage", () => {
    const html = render(chain());
    expect(html).toContain("WHO WILL APPROVE THIS REQUEST");
    expect(html).toContain("Vikram Rao — Delivery Manager");
    expect(html).toContain("Asha Menon — HR Business Partner");
    expect(html).not.toContain("I understand");
  });

  it("warns about a missing approver and asks for an explicit acknowledgement", () => {
    const html = render(chain({
      warnings: ["L1 approver: Nobody is assigned."],
      stages: [
        { stage: "l1", label: "L1 approver", status: "missing", user: null, note: "Nobody is assigned." },
        { stage: "l2", label: "L2 HR approver", status: "assigned", user: asha, note: "" },
      ],
    }));
    expect(html).toContain("Not assigned");
    expect(html).toContain("alert-warn");
    expect(html).toContain("I understand and want to submit anyway");
  });

  it("shows why a request cannot be sent and offers no way around it", () => {
    const html = render(chain({
      can_submit: false, blocking: ["Nobody is available to approve this request. Ask HR to assign an approver first."],
      stages: [
        { stage: "l1", label: "L1 approver", status: "missing", user: null, note: "" },
        { stage: "l2", label: "L2 HR approver", status: "missing", user: null, note: "" },
      ],
    }));
    expect(html).toContain("alert-error");
    expect(html).toContain("Nobody is available");
    expect(html).not.toContain("I understand");
  });

  it("explains that a manager's leave skips L1", () => {
    const html = render(chain({
      stages: [
        { stage: "l1", label: "L1 approver", status: "skipped", user: null, note: "Managers' leave goes straight to HR." },
        { stage: "l2", label: "L2 HR approver", status: "assigned", user: asha, note: "" },
      ],
    }));
    expect(html).toContain("not needed");
  });
});
