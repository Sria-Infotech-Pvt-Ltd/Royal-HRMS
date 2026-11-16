// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import HomePayslipsPanel from "./HomePayslipsPanel";

afterEach(() => cleanup());

const panel = <HomePayslipsPanel payslips={[]} form16FyStartYear={2025} onViewAll={vi.fn()} />;

describe("HomePayslipsPanel: Employment letter", () => {
  it("downloads the employment letter PDF, the same one the Employment tab offers", () => {
    render(panel);
    const letter = screen.getByRole("link", { name: /Employment letter/ });
    expect(letter.getAttribute("href")).toBe(`${API_BASE}${API.employees.myEmploymentLetterPdf}`);
    expect(letter.getAttribute("target")).toBeNull();
  });

  it("does not open a request form or the Document Center for the letter", () => {
    render(panel);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("link", { name: /Employment letter/ }).getAttribute("href")).not.toContain("/dashboard/documents");
  });

  it("downloads Form 16 for the previous financial year, not the Document Center", () => {
    render(panel);
    const form16 = screen.getByRole("link", { name: /Form 16/ });
    expect(form16.getAttribute("href")).toBe(`${API_BASE}${API.payroll.form16Pdf(2025)}`);
    expect(form16.getAttribute("href")).not.toContain("/dashboard/documents");
  });

  it("hides Form 16 when there is no closed financial year yet", () => {
    render(<HomePayslipsPanel payslips={[]} form16FyStartYear={null} onViewAll={vi.fn()} />);
    expect(screen.queryByRole("link", { name: /Form 16/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Employment letter/ })).toBeTruthy();
  });
});
