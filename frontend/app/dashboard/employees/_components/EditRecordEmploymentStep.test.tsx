// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import { EMPTY_EMPLOYMENT, type EmploymentDraft } from "../../hire/[hireActionId]/_components/EmploymentStep";

// The REAL step + REAL useEmploymentLookups; only the network is replaced.
const get = vi.fn();
vi.mock("@/lib/clientApi", () => ({
  default: { get: (...args: unknown[]) => get(...args) },
  isSessionKnownExpired: () => false,
}));

import EditRecordEmploymentStep from "./EditRecordEmploymentStep";

const BRANCHES = [
  { id: 1, branch_name: "Kondapur", branch_code: "KDP01" },
  { id: 2, branch_name: "Mulugu", branch_code: "MLG01" },
];
const paged = <T,>(results: T[]) => ({ data: { data: { results } } });

type BranchReply = "ok" | "empty" | "fail";
function mockNetwork(branchReply: BranchReply) {
  get.mockImplementation(async (url: string) => {
    if (url === API.employees.branches) {
      if (branchReply === "fail") throw new Error("403");
      return paged(branchReply === "empty" ? [] : BRANCHES);
    }
    return paged([]);
  });
}

// The lookup hook caches for 5 minutes at module level; moving the clock on makes every test fetch afresh.
let clock = Date.now();
beforeEach(() => {
  clock += 10 * 60 * 1000;
  vi.spyOn(Date, "now").mockImplementation(() => clock);
  get.mockReset();
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const draftOf = (over: Partial<EmploymentDraft> = {}): EmploymentDraft => ({
  ...EMPTY_EMPLOYMENT, employment_type: "Full-time", branch: "Kondapur", work_location: "Plot 14, Kondapur",
  work_mode: "office", notice_period_days: "30", ...over,
});

/** Behaves like EditRecordModal: owns the draft, hands it down, and records every draft the step emits. */
function mount(initial: EmploymentDraft) {
  const emitted: EmploymentDraft[] = [];
  function Harness() {
    const [draft, setDraft] = useState(initial);
    return <EditRecordEmploymentStep value={draft} onChange={next => { emitted.push(next); setDraft(next); }} positionTitle="Engineer" orgUnitName="Tech" />;
  }
  render(<Harness />);
  return emitted;
}

const branchSelect = () => screen.getByText("Company Code").closest(".f")!.querySelector("select") as HTMLSelectElement;
const optionLabels = () => Array.from(branchSelect().options).map(option => option.textContent);

describe("EditRecordEmploymentStep > Company Code", () => {
  it("lists the active branches with their codes, asking the API for active ones only", async () => {
    mockNetwork("ok");
    mount(draftOf());
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    expect(optionLabels()).toEqual(["Kondapur (KDP01)", "Mulugu (MLG01)"]);
    const branchCall = get.mock.calls.find(([url]) => url === API.employees.branches);
    expect(branchCall?.[1]).toEqual({ params: { page_size: 50, status: "active" } });
  });

  it("selects the employee's current branch by default", async () => {
    mockNetwork("ok");
    mount(draftOf({ branch: "Mulugu" }));
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    expect(branchSelect().value).toBe("Mulugu");
  });

  it("emits the new branch and leaves every other field of the draft untouched", async () => {
    mockNetwork("ok");
    const emitted = mount(draftOf());
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    fireEvent.change(branchSelect(), { target: { value: "Mulugu" } });
    expect(branchSelect().value).toBe("Mulugu");
    expect(emitted).toHaveLength(1);
    expect(emitted[0]).toEqual({ ...draftOf(), branch: "Mulugu" });
  });

  it("keeps working with an empty branch list: the current branch stays selectable", async () => {
    mockNetwork("empty");
    mount(draftOf());
    await waitFor(() => expect(get).toHaveBeenCalledWith(API.employees.branches, expect.anything()));
    expect(optionLabels()).toEqual(["Kondapur"]);
    expect(branchSelect().value).toBe("Kondapur");
  });

  it("keeps working when the branch lookup fails (e.g. no permission): current branch kept, rest of the step intact", async () => {
    mockNetwork("fail");
    const emitted = mount(draftOf());
    await waitFor(() => expect(get).toHaveBeenCalledWith(API.employees.branches, expect.anything()));
    expect(optionLabels()).toEqual(["Kondapur"]);
    expect(branchSelect().value).toBe("Kondapur");
    fireEvent.change(screen.getByText("Work mode").closest(".f")!.querySelector("select")!, { target: { value: "remote" } });
    expect(emitted.at(-1)?.work_mode).toBe("remote");
  });

  it("keeps an employee's current branch visible even if it is no longer in the active list", async () => {
    mockNetwork("ok");
    mount(draftOf({ branch: "Old Closed Branch" }));
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    expect(optionLabels()).toEqual(["Old Closed Branch", "Kondapur (KDP01)", "Mulugu (MLG01)"]);
    expect(branchSelect().value).toBe("Old Closed Branch");
  });

  it("offers no blank choice once a branch is set (a blank save would clear the Company Code), but does when none is", async () => {
    mockNetwork("ok");
    mount(draftOf());
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    expect(optionLabels()).not.toContain("Select");
    cleanup();

    mockNetwork("ok");
    mount(draftOf({ branch: "" }));
    await waitFor(() => expect(optionLabels()).toContain("Mulugu (MLG01)"));
    expect(optionLabels()[0]).toBe("Select");
  });
});
