// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { InvalidPunch } from "@/types/attendance";

const row: InvalidPunch = {
  id: "p1", employee_name: "Kondapur Employee", employee_code: "EMP042", source: "Manual", device_id: "—",
  raw_time: "2026-11-20 13:00:00", biometric_id: "—", issue: "Punch time is in the future", issue_type: "future",
  suggested_match: "Add IN punch", branch: "Kondapur",
};

vi.mock("@/hooks/usePermission", () => ({ usePermission: () => true }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: () => ({ data: { count: 1, page: 1, total_pages: 1, results: [row] }, loading: false, error: null, refetch: vi.fn() }),
}));
vi.mock("@/lib/api/endpoints", () => ({ API: { attendance: { invalidPunches: "/attendance/invalid-punches/" } } }));
vi.mock("./AssignPunchModal", () => ({ default: () => null }));
vi.mock("./DiscardPunchModal", () => ({ default: () => null }));
vi.mock("./ConvertPunchModal", () => ({ default: () => null }));

import InvalidPunchesTab from "./InvalidPunchesTab";

afterEach(() => cleanup());

describe("Invalid Punches list", () => {
  it("says whose punch each row is, with their code and how it was made", () => {
    render(<InvalidPunchesTab />);
    expect(screen.getByRole("columnheader", { name: "Employee" })).toBeTruthy();
    expect(screen.getByText("Kondapur Employee")).toBeTruthy();
    expect(screen.getByText("EMP042 · Manual")).toBeTruthy();
    expect(screen.getByText("Punch time is in the future")).toBeTruthy();
  });
});
