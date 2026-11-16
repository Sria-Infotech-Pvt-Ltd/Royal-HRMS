// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import HomePayslipsPanel from "./HomePayslipsPanel";

afterEach(() => cleanup());

const panel = <HomePayslipsPanel payslips={[]} showForm16={true} onViewAll={vi.fn()} />;

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

  it("keeps Form 16 as a link to the Document Center", () => {
    render(panel);
    expect(screen.getByRole("link", { name: /Form 16/ }).getAttribute("href")).toBe("/dashboard/documents");
  });
});
