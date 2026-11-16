// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import HomePayslipsPanel from "./HomePayslipsPanel";

const showToast = vi.fn();
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast }) }));
vi.mock("../../my-requests/_components/EmployeeRequestModal", () => ({
  default: ({ onClose, onSubmitted }: { onClose: () => void; onSubmitted: () => void }) => (
    <div role="dialog" aria-label="employment-letter-request">
      <button onClick={onSubmitted}>submit</button>
      <button onClick={onClose}>close</button>
    </div>
  ),
}));

afterEach(() => { cleanup(); showToast.mockReset(); });

const panel = <HomePayslipsPanel payslips={[]} showForm16={true} onViewAll={vi.fn()} />;

describe("HomePayslipsPanel: Employment letter", () => {
  it("opens the request form instead of going to the Document Center", () => {
    render(panel);
    expect(screen.queryByRole("dialog")).toBeNull();
    const letter = screen.getByRole("button", { name: /Employment letter/ });
    expect(letter.getAttribute("href")).toBeNull();
    fireEvent.click(letter);
    expect(screen.getByRole("dialog", { name: "employment-letter-request" })).toBeTruthy();
  });

  it("closes the form and confirms once the request is sent", () => {
    render(panel);
    fireEvent.click(screen.getByRole("button", { name: /Employment letter/ }));
    fireEvent.click(screen.getByRole("button", { name: "submit" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(showToast).toHaveBeenCalledWith("Your employment letter request was sent to HR.", "success");
  });

  it("keeps Form 16 as a link to the Document Center", () => {
    render(panel);
    expect(screen.getByRole("link", { name: /Form 16/ }).getAttribute("href")).toBe("/dashboard/documents");
  });
});
