// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const push = vi.hoisted(() => vi.fn());
const back = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, back }) }));

import DashboardFooter from "./DashboardFooter";
import PrivacyPage from "@/app/dashboard/privacy/page";
import SecurityPage from "@/app/dashboard/security/page";

beforeEach(() => { push.mockReset(); back.mockReset(); });
afterEach(cleanup);

describe("the footer", () => {
  it("shows the AIRA mark (not two letters) and sends every link somewhere", () => {
    const { container } = render(<DashboardFooter />);
    expect(container.querySelector(".footer-logo svg")).toBeTruthy();
    expect(container.querySelector(".footer-logo")?.textContent).toBe("");
    for (const [name, path] of [
      ["Privacy & retention", "/dashboard/privacy"], ["Security", "/dashboard/security"],
      ["Audit trail", "/dashboard/settings/audit"], ["Support", "/dashboard/ess?tab=hrHelp"],
    ]) {
      push.mockClear();
      fireEvent.click(screen.getByRole("button", { name }));
      expect(push).toHaveBeenCalledWith(path);
    }
  });
});

describe("Privacy & retention", () => {
  it("says what is kept, for how long and who sees it, using the retention the employee record already states", () => {
    render(<PrivacyPage />);
    expect(screen.getByText("Privacy & retention", { selector: ".page-title" })).toBeTruthy();
    for (const title of ["What is kept, and why", "How long it is kept", "Who can see it", "Your questions and requests"]) expect(screen.getByRole("region", { name: title })).toBeTruthy();
    expect(screen.getByText(/kept for 8 years, for Income Tax and EPF/)).toBeTruthy();
    expect(screen.getByText(/Statutory records cannot be deleted early/)).toBeTruthy();
    expect(screen.getByText(/deleted 30 days after the import finishes/)).toBeTruthy();
  });

  it("does not claim a certification or a guarantee, and points to HR for the full policy", () => {
    const { container } = render(<PrivacyPage />);
    expect(container.textContent).not.toMatch(/ISO|SOC ?2|GDPR|certified|guarantee/i);
    expect(container.textContent).toContain("Your company's own policy and the law apply");
  });
});

describe("Security", () => {
  it("states the real limits: 5 tries then 30 minutes, 10-minute codes, 72-hour one-time links, 15-minute and 7-day sessions", () => {
    render(<SecurityPage />);
    expect(screen.getByText("Security", { selector: ".page-title" })).toBeTruthy();
    expect(screen.getByText(/5 wrong passwords your account is locked for 30 minutes/)).toBeTruthy();
    expect(screen.getByText(/work for 10 minutes, allow 5 tries/)).toBeTruthy();
    expect(screen.getByText(/works once, for 72 hours/)).toBeTruthy();
    expect(screen.getByText(/up to 7 days/)).toBeTruthy();
    expect(screen.getByText(/lasts 15 minutes/)).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Who can do what" })).getByText(/cannot approve your own leave or expense requests/)).toBeTruthy();
  });

  it("is not presented as a certification", () => {
    const { container } = render(<SecurityPage />);
    expect(container.textContent).toContain("It is not a certification or a guarantee");
  });
});

describe("both pages", () => {
  it.each([["Privacy", PrivacyPage], ["Security", SecurityPage]])("%s has Back on the right and a Contact HR link", (_name, Page) => {
    render(<Page />);
    const actions = document.querySelector(".page-actions") as HTMLElement;
    fireEvent.click(within(actions).getByRole("button", { name: /Back/ }));
    expect(back).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Contact HR" }));
    expect(push).toHaveBeenCalledWith("/dashboard/ess?tab=hrHelp");
  });
});
