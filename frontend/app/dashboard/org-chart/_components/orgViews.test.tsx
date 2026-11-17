// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OrgUnit, Position } from "@/types/orgStructure";
import { findAttention, rollupUnits } from "@/lib/orgStructureStats";
import OrgChartView from "./OrgChartView";
import OrgOverview from "./OrgOverview";
import OrgReportingChart from "./OrgReportingChart";
import OrgTree from "./OrgTree";

afterEach(() => cleanup());

function unit(id: string, name: string, parent: string | null): OrgUnit {
  return { id, name, code: id, parent, cost_center: "", is_active: true, is_department_level: false, position_count: 0, child_count: 0, created_at: "", updated_at: "" };
}
function seat(id: string, orgUnit: string, options: { holder?: string; chief?: boolean } = {}): Position {
  return {
    id, org_unit: orgUnit, org_unit_name: "", job_template: null, job_template_name: null, title: `Seat ${id}`, grade: "",
    is_chief: options.chief ?? false, is_active: true,
    holder: options.holder ? `emp-${id}` : null, holder_name: options.holder ?? null, holder_employee_id: null, holder_since: null,
    scheduled: null, branch: null, branch_name: null, reports_to: null, created_at: "", updated_at: "",
  };
}

const units = [unit("co", "Company", null), unit("fin", "Finance", "co"), unit("hr", "People Ops", "co"), unit("acc", "Accounts", "fin")];
const positions = [
  seat("1", "co", { holder: "Asha Rao", chief: true }),
  seat("2", "fin", { chief: true }),
  seat("3", "hr", { holder: "Ravi Kumar" }),
  seat("4", "acc", { holder: "Meena Iyer" }),
];
const rollups = rollupUnits(units, positions);

describe("OrgChartView", () => {
  it("draws a box per unit with its head, headcount and open seats, and opens deeper levels on demand", () => {
    const onSelectUnit = vi.fn();
    render(<OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={null} onSelectUnit={onSelectUnit} />);
    expect(screen.getByText("Company")).toBeTruthy();
    expect(screen.getByText("Asha Rao")).toBeTruthy();
    expect(screen.getByText("Head seat vacant")).toBeTruthy();       // Finance's chief seat is empty
    expect(screen.getAllByText("No head set")).toHaveLength(2);      // People Ops and Accounts have a seat but no chief
    expect(screen.getByText("Accounts")).toBeTruthy();               // the first three levels start open
    fireEvent.click(screen.getByText("Finance"));
    expect(onSelectUnit).toHaveBeenCalledWith("fin");
  });

  it("collapses everything back to the top unit", () => {
    render(<OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={null} onSelectUnit={() => undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "Collapse all" }));
    expect(screen.queryByText("Finance")).toBeNull();
    expect(screen.getByText("Company")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Expand all" }));
    expect(screen.getByText("Accounts")).toBeTruthy();
  });

  it("zooms in and out", () => {
    render(<OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={null} onSelectUnit={() => undefined} />);
    expect(screen.getByText("100%")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Zoom out" }));
    expect(screen.getByText("85%")).toBeTruthy();
  });
});

describe("OrgChartView search and seats", () => {
  it("highlights matches, dims the rest and opens the path to a match", () => {
    const { container } = render(<OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={null} onSelectUnit={() => undefined} />);
    fireEvent.change(screen.getByLabelText("Search the chart"), { target: { value: "meena" } });
    expect(container.querySelectorAll(".oc-box-hit")).toHaveLength(1);      // Accounts holds Meena Iyer
    expect(container.querySelectorAll(".oc-dim").length).toBeGreaterThan(0);  // People Ops does not
  });

  it("lists each unit's seats and who holds them when Show seats is on", () => {
    render(<OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={null} onSelectUnit={() => undefined} />);
    expect(screen.queryByText("Seat 3")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Show seats/ }));
    expect(screen.getByText("Seat 3")).toBeTruthy();
  });
});

describe("OrgReportingChart", () => {
  const reporting = [
    seat("1", "co", { holder: "Asha Rao", chief: true }),
    { ...seat("2", "fin", { holder: "Ravi Kumar" }), reports_to: { position_id: "1", title: "Seat 1", holder_name: "Asha Rao" } },
    { ...seat("3", "acc"), reports_to: { position_id: "2", title: "Seat 2", holder_name: "Ravi Kumar" } },
    // A and B report to each other: neither may vanish from the chart.
    { ...seat("4", "hr", { holder: "Loop A" }), reports_to: { position_id: "5", title: "Seat 5", holder_name: null } },
    { ...seat("5", "hr", { holder: "Loop B" }), reports_to: { position_id: "4", title: "Seat 4", holder_name: null } },
  ];

  it("draws each position under the one it reports to, flags vacant seats, and keeps looped seats visible", () => {
    const onSelectPosition = vi.fn();
    render(<OrgReportingChart positions={reporting} selectedPositionId={null} onSelectPosition={onSelectPosition} />);
    for (const title of ["Seat 1", "Seat 2", "Seat 3", "Seat 4", "Seat 5"]) expect(screen.getByText(title)).toBeTruthy();
    expect(screen.getByText("Vacant")).toBeTruthy();                       // Seat 3 has nobody in it
    fireEvent.click(screen.getByText("Seat 2"));
    expect(onSelectPosition).toHaveBeenCalledWith("2");
  });
});

describe("OrgTree headcount and filter", () => {
  const baseProps = { units, positions, search: "", branchFilter: null, selected: null, onSelect: () => undefined, rollups, command: null };

  it("shows filled/total beside each unit", () => {
    render(<OrgTree {...baseProps} seatFilter="all" />);
    expect(screen.getByText("3/4")).toBeTruthy();   // Company: 4 seats below and including it, 3 filled
  });

  it("with the Vacant filter, shows only units with an open seat and the open seats", () => {
    render(<OrgTree {...baseProps} seatFilter="vacant" />);
    expect(screen.getByText("Seat 2")).toBeTruthy();
    expect(screen.queryByText("Seat 3")).toBeNull();
    expect(screen.queryByText("People Ops")).toBeNull();
  });

  it("highlights the searched text", () => {
    const { container } = render(<OrgTree {...baseProps} search="fin" seatFilter="all" />);
    expect(container.querySelector("mark")?.textContent?.toLowerCase()).toBe("fin");
  });
});

describe("OrgOverview", () => {
  it("lists the gaps and jumps to a unit when one is clicked", () => {
    const onSelectUnit = vi.fn();
    render(<OrgOverview attention={findAttention(units, rollups)} onSelectUnit={onSelectUnit} />);
    expect(screen.getByText("Head seat vacant")).toBeTruthy();
    expect(screen.getByText("No head set")).toBeTruthy();
    fireEvent.click(screen.getAllByText("People Ops")[0]);
    expect(onSelectUnit).toHaveBeenCalledWith("hr");
  });

  it("says so when nothing needs attention", () => {
    render(<OrgOverview attention={{ withoutChief: [], chiefVacant: [], empty: [], mostVacant: [] }} onSelectUnit={() => undefined} />);
    expect(screen.getByText(/Every unit has a head/)).toBeTruthy();
  });
});
