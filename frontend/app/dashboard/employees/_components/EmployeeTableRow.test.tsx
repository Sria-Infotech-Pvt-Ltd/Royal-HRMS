// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { DirectoryStatusLabel, Employee } from "../_data";

// The REAL row (status pill, click handling); the dialogs, menu, avatar, router and permission lookup are stubs.
let allowed = true;
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/hooks/usePermission", () => ({ usePermission: () => allowed }));
vi.mock("./Avatar", () => ({ default: () => null }));
vi.mock("./EmployeeRowActionsMenu", () => ({ default: () => null }));
vi.mock("./PerformActionModal", () => ({ default: () => null }));
vi.mock("./OnboardingHistoryModal", () => ({
  default: ({ employeeName, onClose }: { employeeName: string; onClose: () => void }) => (
    <div role="dialog" aria-label="onboarding-history">
      <span>{employeeName}</span>
      <button type="button">Resend Onboarding Email</button>
      <button type="button" onClick={onClose}>Close history</button>
    </div>
  ),
}));

import EmployeeTableRow from "./EmployeeTableRow";
import { canResendOnboardingEmail } from "../_data";

beforeEach(() => { allowed = true; });
afterEach(() => cleanup());

const person = (over: Partial<Employee> = {}): Employee => ({
  id: "10000001", uuid: "uuid-1", code: "10000001", firstName: "Asha", middleName: "", lastName: "Rao", email: "asha@example.com",
  phone: "", department: "Web", designation: "Developer", dateOfJoining: "2026-11-01", dateOfBirth: "1995-01-01", location: "Hyderabad",
  gender: "female", status: "onboarding", awaitingActivation: true, needsOnboardingData: false, employmentStatus: "probation",
  confirmationDate: null, details: {}, tables: {}, ...over,
});

function mount(employee: Employee, props: { canEdit?: boolean } = {}) {
  const onOpen = vi.fn();
  render(
    <EmployeeTableRow
      employee={employee} canEditOnboarding canEdit={props.canEdit ?? true} toggling={false}
      onOpen={onOpen} onToggleStatus={vi.fn()} onActionApplied={vi.fn()}
    />,
  );
  return { onOpen };
}

describe("canResendOnboardingEmail", () => {
  it.each<[DirectoryStatusLabel, boolean]>([
    ["Onboarding", true], ["Awaiting activation", true], ["Active", false], ["Notice Period", false], ["Exited", false],
  ])("%s -> %s", (label, expected) => expect(canResendOnboardingEmail(label)).toBe(expected));
});

describe("Employees list > the status pill that opens the invitation email", () => {
  it.each([
    ["Awaiting activation", { awaitingActivation: true }],
    ["Onboarding", { awaitingActivation: false }],
  ])("is clickable for %s, with a hint of what it does", (label, over) => {
    mount(person(over));
    const pill = screen.getByRole("button", { name: "Onboarding history for Asha Rao" });
    expect(pill.textContent).toContain(label);
    expect(pill.getAttribute("title")).toBe("Onboarding history, and resend the invitation email");
  });

  it("opens the history dialog (with Resend Onboarding Email) for someone awaiting activation", () => {
    mount(person());
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Onboarding history for Asha Rao" }));
    expect(screen.getByRole("dialog", { name: "onboarding-history" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Resend Onboarding Email" })).toBeTruthy();
  });

  it("does not also open the employee's detail panel when the pill is clicked", () => {
    const { onOpen } = mount(person());
    fireEvent.click(screen.getByRole("button", { name: "Onboarding history for Asha Rao" }));
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("does not open the employee's detail panel for clicks inside the dialog either (portal clicks bubble to the row)", () => {
    const { onOpen } = mount(person());
    fireEvent.click(screen.getByRole("button", { name: "Onboarding history for Asha Rao" }));
    fireEvent.click(screen.getByRole("button", { name: "Resend Onboarding Email" }));
    fireEvent.click(screen.getByRole("button", { name: "Close history" }));
    expect(onOpen).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();            // and Close did close it
  });

  it("still opens the employee when the name is clicked, as before", () => {
    const { onOpen } = mount(person());
    fireEvent.click(screen.getByText("Asha Rao"));
    expect(onOpen).toHaveBeenCalledWith("10000001");
  });

  it("is a plain pill, not a button, for an active employee, and clicking it opens the employee as before", () => {
    const { onOpen } = mount(person({ status: "active", awaitingActivation: false }));
    expect(screen.queryByRole("button", { name: /Onboarding history/ })).toBeNull();
    fireEvent.click(screen.getByText("Active"));
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("is a plain pill for someone who has left", () => {
    mount(person({ status: "inactive", awaitingActivation: false }));
    expect(screen.queryByRole("button", { name: /Onboarding history/ })).toBeNull();
  });

  it("is a plain pill without the permission to manage onboarding", () => {
    allowed = false;
    mount(person());
    expect(screen.queryByRole("button", { name: /Onboarding history/ })).toBeNull();
    expect(screen.getByText("Awaiting activation")).toBeTruthy();
  });

  it("is a plain pill when the person cannot edit employees", () => {
    mount(person(), { canEdit: false });
    expect(screen.queryByRole("button", { name: /Onboarding history/ })).toBeNull();
  });

  it("is a plain pill for a row that has no backend id to look the history up with", () => {
    mount(person({ uuid: undefined }));
    expect(screen.queryByRole("button", { name: /Onboarding history/ })).toBeNull();
  });
});

describe("Employees list > the Resend invite button", () => {
  it.each([
    ["Awaiting activation", { awaitingActivation: true }],
    ["Onboarding", { awaitingActivation: false }],
  ])("is always there for someone still onboarding (%s), and opens the history to resend", (_label, over) => {
    mount(person(over));
    fireEvent.click(screen.getByRole("button", { name: "Resend invite to Asha Rao" }));
    expect(screen.getByRole("dialog", { name: "onboarding-history" })).toBeTruthy();
  });

  it("does not also open the employee's detail panel when it is clicked", () => {
    const { onOpen } = mount(person());
    fireEvent.click(screen.getByRole("button", { name: "Resend invite to Asha Rao" }));
    expect(onOpen).not.toHaveBeenCalled();
  });

  it("is shown but switched off, with the reason, for someone without the permission", () => {
    allowed = false;
    mount(person());
    const button = screen.getByRole("button", { name: "Resend invite to Asha Rao" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("title")).toContain("You need permission");
    fireEvent.click(button);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("is shown but switched off when the person cannot edit employees", () => {
    mount(person(), { canEdit: false });
    expect((screen.getByRole("button", { name: "Resend invite to Asha Rao" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("is not shown for an active employee or someone who has left", () => {
    mount(person({ status: "active", awaitingActivation: false }));
    expect(screen.queryByRole("button", { name: /Resend invite/ })).toBeNull();
    cleanup();
    mount(person({ status: "inactive", awaitingActivation: false }));
    expect(screen.queryByRole("button", { name: /Resend invite/ })).toBeNull();
  });
});
