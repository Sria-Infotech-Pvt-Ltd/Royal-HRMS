// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import RejectReasonModal from "./RejectReasonModal";

vi.mock("@/components/Modal", () => ({
  default: ({ title, children }: { title: string; children: React.ReactNode }) => <div role="dialog" aria-label={title}>{children}</div>,
}));

afterEach(() => cleanup());

function mount(props: Partial<React.ComponentProps<typeof RejectReasonModal>> = {}) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(<RejectReasonModal employeeName="Asha Rao" isSaving={false} serverError="" onSubmit={onSubmit} onCancel={onCancel} {...props} />);
  return { onSubmit, onCancel };
}

describe("RejectReasonModal: the Face ID wording is unchanged", () => {
  it("uses the Face ID registration title, label and button by default", () => {
    mount();
    expect(screen.getByRole("dialog", { name: "Reject Face ID registration — Asha Rao" })).toBeTruthy();
    expect(screen.getByLabelText("Reason (the employee will see this)")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reject registration" })).toBeTruthy();
  });

  it("refuses an empty reason with the Face ID message and sends nothing", () => {
    const { onSubmit } = mount();
    fireEvent.click(screen.getByRole("button", { name: "Reject registration" }));
    expect(screen.getByRole("alert").textContent).toBe("Please give a reason for rejecting this Face ID registration.");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("sends the trimmed reason", () => {
    const { onSubmit } = mount();
    fireEvent.change(screen.getByLabelText("Reason (the employee will see this)"), { target: { value: "  Blurry photo  " } });
    fireEvent.click(screen.getByRole("button", { name: "Reject registration" }));
    expect(onSubmit).toHaveBeenCalledWith("Blurry photo");
  });

  it("shows the busy label and disables the buttons while saving", () => {
    mount({ isSaving: true });
    expect((screen.getByRole("button", { name: "Rejecting…" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Cancel" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows the server's error inside the dialog", () => {
    mount({ serverError: "Already decided." });
    expect(screen.getByRole("alert").textContent).toBe("Already decided.");
  });
});

describe("RejectReasonModal: other workflows can word it themselves", () => {
  const wording = {
    title: "Send timesheet back", fieldLabel: "Reason (the employee will see this)", actionLabel: "Send back", busyLabel: "Sending…",
    requiredMessage: "Please give a reason for sending this timesheet back.",
  };

  it("uses the supplied title, button and required message", () => {
    const { onSubmit } = mount({ wording });
    expect(screen.getByRole("dialog", { name: "Send timesheet back — Asha Rao" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    expect(screen.getByRole("alert").textContent).toBe("Please give a reason for sending this timesheet back.");
    expect(onSubmit).not.toHaveBeenCalled();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Wrong project" } });
    fireEvent.click(screen.getByRole("button", { name: "Send back" }));
    expect(onSubmit).toHaveBeenCalledWith("Wrong project");
  });

  it("a part of the wording can be overridden and the rest stays", () => {
    mount({ wording: { actionLabel: "Send back" } });
    expect(screen.getByRole("dialog", { name: "Reject Face ID registration — Asha Rao" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send back" })).toBeTruthy();
  });
});
