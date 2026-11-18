// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { OnboardingHistory, OnboardingStateCode } from "@/types/onboardingHistory";

const mock = vi.hoisted(() => ({ history: null as unknown, resend: vi.fn() }));
vi.mock("@/hooks/useOnboardingHistory", () => ({ useOnboardingHistory: () => ({ history: mock.history, loading: false, error: null, resend: mock.resend, isResending: false, resendError: null }) }));
vi.mock("@/components/Modal", () => ({ default: ({ children }: { children: React.ReactNode }) => <div role="dialog">{children}</div> }));
vi.mock("@/lib/formatDate", () => ({ formatDateTime: () => "when" }));

import OnboardingHistoryModal from "./OnboardingHistoryModal";

const historyOf = (code: OnboardingStateCode): OnboardingHistory => ({
  employee_name: "Asha Rao", email: "asha@example.com", is_onboarding: code !== "active",
  state: { code, message: `state ${code}`, can_resend: code !== "active" }, timeline: [], resend_limit_per_hour: 5, invite_status: null, invite_sent_at: null, invite_expires_at: null,
});

afterEach(() => { cleanup(); mock.resend.mockReset(); });

describe("the onboarding history window", () => {
  it.each<OnboardingStateCode>(["email_failed", "link_expired", "link_opened", "not_logged_in", "awaiting_login"])("offers Resend Onboarding Email when the state is %s", code => {
    mock.history = historyOf(code);
    render(<OnboardingHistoryModal employeeUuid="u1" employeeName="Asha Rao" onClose={vi.fn()} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Resend Onboarding Email" }));
    expect(mock.resend).toHaveBeenCalledWith(undefined);
  });

  it("does not offer it once onboarding is complete", () => {
    mock.history = historyOf("active");
    render(<OnboardingHistoryModal employeeUuid="u1" employeeName="Asha Rao" onClose={vi.fn()} onChanged={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Resend Onboarding Email" })).toBeNull();
  });

  it("sends a corrected address when one is typed", () => {
    mock.history = historyOf("email_failed");
    render(<OnboardingHistoryModal employeeUuid="u1" employeeName="Asha Rao" onClose={vi.fn()} onChanged={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Correct email address" }));
    fireEvent.change(screen.getByPlaceholderText("name@company.com"), { target: { value: "fixed@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Resend Onboarding Email" }));
    expect(mock.resend).toHaveBeenCalledWith("fixed@example.com");
  });
});
