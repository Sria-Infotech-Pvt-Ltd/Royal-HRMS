// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({ rows: null as Array<Record<string, unknown>> | null, error: null as string | null }));
const put = vi.hoisted(() => vi.fn());
const push = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/lib/clientApi", () => ({ default: { put } }));
vi.mock("@/lib/api/endpoints", () => ({ API: { settings: { employeeCodeSeries: "/series/", employeeCodeSeriesDetail: (type: string) => `/series/${type}/` } } }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: mock.rows, loading: !mock.rows && !mock.error, error: mock.error, refetch: vi.fn() }) }));

import { findOverlaps, healthOf, idsLeft, sortRows, summarise, usageColour, validateSeries, type SeriesRow } from "./_components/employeeCodeView";
import EmployeeCodePage from "./page";

const ROW = (type: string, name: string, start: number, overrides: Record<string, unknown> = {}) => ({
  employment_type: type, employment_type_display: name, range_start: start, range_end: start + 9_999_999, next_sequence: start + 1, format_description: "", usage_percent: 0, is_exhausted: false, ...overrides,
});

beforeEach(() => {
  mock.rows = [ROW("permanent", "Permanent", 10000000, { next_sequence: 10000003 }), ROW("contract", "Contract", 20000000), ROW("intern", "Intern", 50000000, { usage_percent: 95 })];
  mock.error = null; put.mockReset(); push.mockReset();
});
afterEach(cleanup);

const row = (name: string) => within(screen.getByRole("row", { name }));
const box = (name: string, label: string) => screen.getByLabelText(`${name} ${label}`) as HTMLInputElement;
const order = () => screen.getAllByRole("row").slice(1).map(each => each.getAttribute("aria-label"));

describe("ID range rules", () => {
  it("keeps the long-standing checks and wording", () => {
    const good = { range_start: 100, range_end: 200, next_sequence: 101 };
    expect(validateSeries({ range_start: "100", range_end: "200", next_sequence: "101" }, good)).toEqual({});
    expect(validateSeries({ range_start: "", range_end: "200", next_sequence: "101" }, good).range_start).toBe("Required — whole number.");
    expect(validateSeries({ range_start: "100", range_end: "100", next_sequence: "101" }, { ...good, range_end: 100 }).range_end).toBe("Must be greater than range start.");
    expect(validateSeries({ range_start: "100", range_end: "200", next_sequence: "300" }, { ...good, next_sequence: 300 }).next_sequence).toContain("Must be between 101 and 200");
    expect(validateSeries({ range_start: "100", range_end: "200", next_sequence: "201" }, { ...good, next_sequence: 201 })).toEqual({});
  });
  it("counts what is left and rates how healthy a range is", () => {
    expect(idsLeft({ range_start: 1, range_end: 10, next_sequence: 4 })).toBe(7);
    expect(idsLeft({ range_start: 1, range_end: 10, next_sequence: 11 })).toBe(0);
    expect(healthOf(10, false)).toBe("healthy");
    expect(healthOf(90, false)).toBe("nearing");
    expect(healthOf(100, true)).toBe("exhausted");
    expect(usageColour(50, false)).toBe("#16A34A");
    expect(usageColour(75, false)).toBe("#EA580C");
    expect(usageColour(95, false)).toBe("#DC2626");
  });
  it("adds up the types, the IDs left and the ranges that need attention", () => {
    expect(summarise(mock.rows as unknown as SeriesRow[])).toEqual({ types: 3, idsLeft: 9_999_997 + 9_999_999 + 9_999_999, nearing: 1 });
  });
  it("finds ranges that share numbers, including ones that only touch at an end", () => {
    expect(findOverlaps([{ type: "a", start: 1, end: 10 }, { type: "b", start: 11, end: 20 }]).size).toBe(0);
    expect([...findOverlaps([{ type: "a", start: 1, end: 10 }, { type: "b", start: 10, end: 20 }, { type: "c", start: 30, end: 40 }])].sort()).toEqual(["a", "b"]);
  });
  it("sorts by name, range or how full, both ways", () => {
    const rows = mock.rows as unknown as SeriesRow[];
    expect(sortRows(rows, "name", "asc").map(r => r.employment_type)).toEqual(["contract", "intern", "permanent"]);
    expect(sortRows(rows, "usage", "desc")[0].employment_type).toBe("intern");
    expect(sortRows(rows, "range_start", "desc")[0].employment_type).toBe("intern");
  });
});

describe("the Employee ID Ranges page", () => {
  it("shows the totals, the map of the number space, and one table row per type", () => {
    render(<EmployeeCodePage />);
    expect(screen.getByLabelText("Summary").textContent).toContain("3 worker types");
    expect(screen.getByLabelText("Summary").textContent).toContain("1 need attention");
    expect(screen.getByRole("img", { name: /Permanent: 10000000 to 19999999$/ })).toBeTruthy();
    expect(order()).toEqual(["Permanent", "Contract", "Intern"]);
    expect(row("Permanent").getByText("10000003")).toBeTruthy();
    expect(row("Intern").getByText("Nearing limit")).toBeTruthy();
    expect(row("Intern").getByRole("progressbar").getAttribute("aria-valuenow")).toBe("95");
  });

  it("sorts when a heading is clicked, and flips on a second click", () => {
    render(<EmployeeCodePage />);
    fireEvent.click(screen.getByRole("button", { name: /Worker type/ }));
    expect(order()).toEqual(["Contract", "Intern", "Permanent"]);
    fireEvent.click(screen.getByRole("button", { name: /Worker type/ }));
    expect(order()).toEqual(["Permanent", "Intern", "Contract"]);
    expect(screen.getByRole("columnheader", { name: /Worker type/ }).getAttribute("aria-sort")).toBe("descending");
    fireEvent.click(screen.getByRole("button", { name: /Used/ }));
    expect(order()[2]).toBe("Intern");
  });

  it("marks a row as unsaved when a number changes, follows it in Next ID, and Reset puts it back", () => {
    render(<EmployeeCodePage />);
    expect((screen.getByRole("button", { name: "Save Permanent" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "10000010" } });
    expect((screen.getByRole("button", { name: "Save Permanent" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getByText("1 unsaved change")).toBeTruthy();
    expect(row("Permanent").getAllByText("10000010").length).toBeGreaterThan(0);
    fireEvent.click(row("Permanent").getByRole("button", { name: "Reset" }));
    expect(box("Permanent", "Next number").value).toBe("10000003");
    expect(screen.queryByText("1 unsaved change")).toBeNull();
  });

  it("moves the map and warns in red when two ranges start to overlap, then clears when fixed", () => {
    render(<EmployeeCodePage />);
    fireEvent.change(box("Contract", "Range from"), { target: { value: "15000000" } });
    expect(screen.getByRole("alert").textContent).toContain("share some of the same numbers");
    expect(screen.getByRole("img", { name: /Contract.*overlaps another range/ })).toBeTruthy();
    expect(row("Permanent").getByText("Overlaps another range")).toBeTruthy();
    fireEvent.change(box("Contract", "Range from"), { target: { value: "20000000" } });
    expect(screen.queryByText(/share some of the same numbers/)).toBeNull();
  });

  it("lets a box be cleared and retyped, and says what is wrong on Enter without sending anything", () => {
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Range to"), { target: { value: "" } });
    expect(box("Permanent", "Range to").value).toBe("");
    fireEvent.keyDown(box("Permanent", "Range to"), { key: "Enter" });
    expect(row("Permanent").getByText("Required — whole number.")).toBeTruthy();
    expect(put).not.toHaveBeenCalled();
  });

  it("shows Exhausted when the next number is past the end of the range", () => {
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "20000000" } });
    expect(row("Permanent").getByText("Exhausted", { selector: "td" })).toBeTruthy();
  });

  it("saves only that type, with the same call as before, and shows it saved", async () => {
    put.mockResolvedValue({ data: { data: ROW("permanent", "Permanent", 10000000, { next_sequence: 10000010 }) } });
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "10000010" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Permanent" }));
    await waitFor(() => expect(put).toHaveBeenCalledWith("/series/permanent/", { range_start: 10000000, range_end: 19999999, next_sequence: 10000010 }));
    await waitFor(() => expect(row("Permanent").getByText("Saved")).toBeTruthy());
    expect(put).toHaveBeenCalledTimes(1);
  });

  it("saves every changed row with Save all, and leaves unchanged rows alone", async () => {
    put.mockImplementation((url: string) => Promise.resolve({ data: { data: url.includes("permanent") ? ROW("permanent", "Permanent", 10000000, { next_sequence: 10000010 }) : ROW("contract", "Contract", 20000000, { next_sequence: 20000005 }) } }));
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "10000010" } });
    fireEvent.change(box("Contract", "Next number"), { target: { value: "20000005" } });
    expect(screen.getByText("2 unsaved changes")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save all" }));
    await waitFor(() => expect(put).toHaveBeenCalledTimes(2));
    expect(put.mock.calls.map(call => call[0]).sort()).toEqual(["/series/contract/", "/series/permanent/"]);
    await waitFor(() => expect(screen.queryByText(/unsaved change/)).toBeNull());
  });

  it("resets every row with Reset all", () => {
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "10000010" } });
    fireEvent.change(box("Contract", "Next number"), { target: { value: "20000005" } });
    fireEvent.click(screen.getByRole("button", { name: "Reset all" }));
    expect(box("Permanent", "Next number").value).toBe("10000003");
    expect(box("Contract", "Next number").value).toBe("20000001");
  });

  it("shows the server's message when it refuses, and keeps what was typed", async () => {
    put.mockRejectedValue({ response: { data: { message: "Ranges overlap." } } });
    render(<EmployeeCodePage />);
    fireEvent.change(box("Permanent", "Next number"), { target: { value: "10000010" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Permanent" }));
    await waitFor(() => expect(row("Permanent").getByRole("alert").textContent).toContain("Ranges overlap."));
    expect(box("Permanent", "Next number").value).toBe("10000010");
  });

  it("shows a placeholder while loading, an error, and goes back to Settings", () => {
    mock.rows = null;
    render(<EmployeeCodePage />);
    expect(screen.getAllByLabelText("Loading").length).toBeGreaterThan(0);
    cleanup();
    mock.error = "Could not load";
    render(<EmployeeCodePage />);
    expect(screen.getByRole("alert").textContent).toContain("Could not load");
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(push).toHaveBeenCalledWith("/dashboard/settings");
  });
});
