// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import EligibilitySection from "./EligibilitySection";
import type { PolicyRuleFields } from "./LeavePoliciesTab";

vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: [], loading: false, error: null, refetch: vi.fn() }) }));

afterEach(() => cleanup());

const rules = {
  applicable_branches: [], applicable_departments: [], applicable_designations: [], applicable_employment_types: [],
  applicable_gender: "female", minimum_service_period: 0, grant_mode: "annual",
} as unknown as PolicyRuleFields;   // only the fields this section reads are needed for these tests

describe("EligibilitySection: how the leave is given", () => {
  it("offers yearly credit and per-case grant, and reports the choice", () => {
    const setField = vi.fn();
    render(<EligibilitySection rules={rules} setField={setField} />);
    const select = screen.getByDisplayValue("Credited to every eligible employee each year") as HTMLSelectElement;
    expect(Array.from(select.options).map(option => option.value)).toEqual(["annual", "on_request"]);
    fireEvent.change(select, { target: { value: "on_request" } });
    expect(setField).toHaveBeenCalledWith("grant_mode", "on_request");
  });

  it("explains what on-request means only when it is chosen", () => {
    const { rerender } = render(<EligibilitySection rules={rules} setField={vi.fn()} />);
    expect(screen.queryByText(/Nobody is credited in advance/)).toBeNull();
    rerender(<EligibilitySection rules={{ ...rules, grant_mode: "on_request" }} setField={vi.fn()} />);
    expect(screen.getByText(/Nobody is credited in advance/)).toBeTruthy();
  });
});
