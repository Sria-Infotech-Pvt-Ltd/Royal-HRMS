// @vitest-environment jsdom
// The "Move employees" wizard end to end: tick people, pick the unit, check the suggested positions, review, confirm.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const post = vi.hoisted(() => vi.fn());
vi.mock("@/lib/clientApi", () => ({ default: { post } }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: vi.fn() }) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: () => ({
    data: {
      results: [
        { employee_id: "E1", full_name: "Asha Rao", designation: "Analyst", org_unit_id: "u-old", is_active: true },
        { employee_id: "E2", full_name: "Ravi Kumar", designation: "Tester", org_unit_id: "u-old", is_active: true },
        { employee_id: "E3", full_name: "Elsewhere Person", designation: "Analyst", org_unit_id: "u-other", is_active: true },
      ],
    },
    loading: false, refetch: vi.fn(),
  }),
}));
vi.mock("@/hooks/useOrgUnitsAndPositions", () => ({
  useOrgUnitsAndPositions: () => ({
    loading: false,
    units: [
      { id: "u-old", name: "Old Unit", parent: null, is_active: true },
      { id: "u-new", name: "New Unit", parent: null, is_active: true },
      { id: "u-other", name: "Other Unit", parent: null, is_active: true },
    ],
    positions: [
      { id: "p-a", org_unit: "u-new", title: "Analyst", grade: "L3", is_active: true, holder: null },
      { id: "p-b", org_unit: "u-new", title: "Lead", grade: "L4", is_active: true, holder: null },
      { id: "p-c", org_unit: "u-new", title: "Analyst", grade: "L3", is_active: true, holder: "someone" },
    ],
  }),
}));

import BulkMoveOrgUnitModal from "./BulkMoveOrgUnitModal";

beforeEach(() => post.mockReset());
afterEach(cleanup);

const button = (name: RegExp) => screen.getByRole("button", { name });

function drag(code: string, target: Element) {
  const store: Record<string, string> = { "application/x-aira-employee": code };
  const dataTransfer = { types: Object.keys(store), getData: (type: string) => store[type] ?? "", setData: () => {}, effectAllowed: "move" };
  fireEvent.dragOver(target, { dataTransfer });
  fireEvent.drop(target, { dataTransfer });
}

describe("BulkMoveOrgUnitModal", () => {
  it("opened from a unit, lists only that unit's people and cannot review until someone has a position", () => {
    render(<BulkMoveOrgUnitModal initialFromUnitId="u-old" onClose={() => {}} onDone={() => {}} />);
    expect(screen.queryByText("Elsewhere Person")).toBeNull();
    expect((button(/^Review move/) as HTMLButtonElement).disabled).toBe(true);
  });

  it("fills the vacant positions by title, then moves everyone after the review", async () => {
    post.mockResolvedValue({ data: { data: { moved: [{ employee_id: "E1", org_unit: "New Unit", position: "Analyst" }, { employee_id: "E2", org_unit: "New Unit", position: "Lead" }], skipped: [] } } });
    const onDone = vi.fn();
    render(<BulkMoveOrgUnitModal initialFromUnitId="u-old" onClose={() => {}} onDone={onDone} />);

    fireEvent.change(screen.getByLabelText(/^New org unit/), { target: { value: "u-new" } });
    expect(screen.getByText("0 of 2 vacant positions filled")).toBeTruthy();   // the held Analyst seat is not offered
    fireEvent.click(screen.getByRole("checkbox", { name: "Choose everyone shown" }));
    expect(screen.getByText("2 of 2 vacant positions filled")).toBeTruthy();

    fireEvent.click(button(/^Review move/));
    expect(screen.getByText("AFTER THE MOVE")).toBeTruthy();
    fireEvent.click(button(/Move 2 employee/));
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
      moves: [{ employee_id: "E1", position_id: "p-a" }, { employee_id: "E2", position_id: "p-b" }],
    }));
    expect(await screen.findByText(/Everyone you chose has moved/)).toBeTruthy();
  });

  it("dragging someone onto a taken position swaps the two people", async () => {
    post.mockResolvedValue({ data: { data: { moved: [], skipped: [] } } });
    render(<BulkMoveOrgUnitModal initialFromUnitId="u-old" onClose={() => {}} onDone={() => {}} />);
    fireEvent.change(screen.getByLabelText(/^New org unit/), { target: { value: "u-new" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Choose everyone shown" }));

    const leadSlot = within(screen.getByRole("region", { name: "New positions" })).getByText("Lead").closest("[role=listitem]");
    if (!leadSlot) throw new Error("no Lead slot");
    drag("E1", leadSlot);   // Asha onto Lead, which Ravi had

    fireEvent.click(button(/^Review move/));
    fireEvent.click(button(/Move 2 employee/));
    await vi.waitFor(() => expect(post).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({
      moves: [{ employee_id: "E1", position_id: "p-b" }, { employee_id: "E2", position_id: "p-a" }],
    }));
  });
});
