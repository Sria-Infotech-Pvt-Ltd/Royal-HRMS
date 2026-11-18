// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import EmailLogRow, { type EmailLogEntry } from "./EmailLogRow";

afterEach(cleanup);

const ROW = (overrides: Partial<EmailLogEntry> = {}): EmailLogEntry => ({
  id: "l1", recipient_email: "asha@example.com", subject: "Welcome", status: "sent", module: "accounts", template_name: "leave_approved",
  triggered_by_name: "System", smtp_settings_name: "Main", is_resend: false, had_attachments: false, has_sensitive_context: false,
  resend_blocked_reason: null, error_message: "", created_at: "2026-11-18T10:00:00Z", ...overrides,
});

function mount(row: EmailLogEntry, props: { canResend?: boolean; isResending?: boolean } = {}) {
  const onResend = vi.fn();
  render(<table><tbody><EmailLogRow row={row} moduleClass="badge-neutral" sentAt="18-11-2026" canResend={props.canResend ?? true} isResending={props.isResending ?? false} onResend={onResend} /></tbody></table>);
  return { onResend };
}

describe("the Resend button on an Email Log row", () => {
  it.each<[string, Partial<EmailLogEntry>]>([
    ["a sent email", { status: "sent" }],
    ["a failed email", { status: "failed", error_message: "550 mailbox unavailable" }],
  ])("is on %s and sends that row", (_name, over) => {
    const { onResend } = mount(ROW(over));
    fireEvent.click(screen.getByRole("button", { name: "Resend to asha@example.com" }));
    expect(onResend).toHaveBeenCalledTimes(1);
    expect(onResend.mock.calls[0][0].id).toBe("l1");
  });

  it("is called Resend invite on an onboarding invitation, sent or failed", () => {
    mount(ROW({ template_name: "onboarding_invite", has_sensitive_context: true }));
    expect(screen.getByRole("button", { name: "Resend to asha@example.com" }).textContent).toContain("Resend invite");
  });

  it("does not also open the row's details when it is clicked", () => {
    mount(ROW());
    fireEvent.click(screen.getByRole("button", { name: "Resend to asha@example.com" }));
    expect(screen.queryByText("Mail account used")).toBeNull();
  });

  it("is shown but switched off, with the reason, without the permission", () => {
    const { onResend } = mount(ROW(), { canResend: false });
    const button = screen.getByRole("button", { name: "Resend to asha@example.com" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.getAttribute("title")).toContain("You need permission");
    fireEvent.click(button);
    expect(onResend).not.toHaveBeenCalled();
  });

  it("shows Resending… and is switched off while it works", () => {
    mount(ROW(), { isResending: true });
    const button = screen.getByRole("button", { name: "Resend to asha@example.com" }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent).toContain("Resending");
  });

  it("says where to re-issue an email that cannot be replayed (a password reset), instead of a button", () => {
    mount(ROW({ template_name: "password_reset_by_admin", has_sensitive_context: true, resend_blocked_reason: "Use Reset password on the employee again." }));
    expect(screen.queryByRole("button", { name: /Resend to/ })).toBeNull();
    expect(screen.getByText("Re-issue from the employee").getAttribute("title")).toContain("Reset password");
  });
});
