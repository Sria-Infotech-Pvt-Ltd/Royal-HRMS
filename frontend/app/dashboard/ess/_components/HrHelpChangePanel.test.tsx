// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import type { HrHelpRequest } from "@/types/hrHelp";
import HrHelpChangePanel from "./HrHelpChangePanel";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
const fields = [{ key: "full_name", section: "Personal details", label: "Full name", kind: "text", max_length: 150, choices: [], full_access_only: false }];
vi.mock("@/hooks/useFetch", () => ({ useFetch: (url: string | null) => ({ data: url ? fields : null, loading: false, error: null, refetch: vi.fn() }) }));

const entry: HrHelpRequest = {
  id: "t1", request_ref: "HR-00001", topic: "profile_correction", topic_display: "Profile correction", priority: "normal",
  priority_display: "Normal", message: "m", status: "open", status_display: "Open", response: "", submitted_by_name: "Durga",
  assigned_to_name: "", created_at: "2026-11-16T07:55:00Z", updated_at: "2026-11-16T07:55:00Z", resolved_at: null,
  submitted_by_code: "10000001", change_field: "full_name", change_label: "Full name", change_old_value: "G.Durga Prasad",
  change_new_value: "Gadde Durga Prasad", change_decision: "", change_applied_at: null, change_needs_system_admin: false, change_suggested_key: "",
};

afterEach(() => { cleanup(); post.mockReset(); });

describe("HrHelpChangePanel", () => {
  it("shows the current and the requested value and links to the employee record", () => {
    render(<HrHelpChangePanel entry={entry} note="" onDecided={vi.fn()} />);
    expect(screen.getByText("G.Durga Prasad")).toBeTruthy();
    expect(screen.getByText("Gadde Durga Prasad")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Open employee record/ }).getAttribute("href")).toBe("/dashboard/employees?open=10000001");
  });

  it("applies the change with the typed note, then tells the row", async () => {
    post.mockResolvedValue({ data: {} });
    const onDecided = vi.fn();
    render(<HrHelpChangePanel entry={entry} note="Checked the ID" onDecided={onDecided} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply requested change" }));
    await waitFor(() => expect(onDecided).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(API.hrHelp.decideChange("t1"), { decision: "approve", note: "Checked the ID" });
  });

  it("declines, and shows the message when the server refuses", async () => {
    post.mockRejectedValue({ response: { data: { message: "Write a short reason before declining, so the employee knows why." } } });
    render(<HrHelpChangePanel entry={entry} note="" onDecided={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Decline" }));
    expect(await screen.findByText(/Write a short reason/)).toBeTruthy();
    expect(post).toHaveBeenCalledWith(API.hrHelp.decideChange("t1"), { decision: "reject", note: "" });
  });

  it("only reports the outcome once it has been decided", () => {
    render(<HrHelpChangePanel entry={{ ...entry, change_decision: "applied" }} note="" onDecided={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Apply requested change" })).toBeNull();
    expect(screen.getByText(/Applied to the employee/)).toBeTruthy();
  });

  it("for an older request, HR types the new value and it is sent with the decision", async () => {
    post.mockResolvedValue({ data: {} });
    const onDecided = vi.fn();
    const older = { ...entry, change_field: "", change_label: "", change_old_value: "", change_new_value: "", change_suggested_key: "full_name" };
    render(<HrHelpChangePanel entry={older} note="Checked" onDecided={onDecided} />);
    const apply = screen.getByRole("button", { name: "Apply requested change" }) as HTMLButtonElement;
    expect(apply.disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText("New full name"), { target: { value: " Gadde Durga Prasad " } });
    expect(apply.disabled).toBe(false);
    fireEvent.click(apply);
    await waitFor(() => expect(onDecided).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(API.hrHelp.decideChange("t1"), { decision: "approve", note: "Checked", new_value: "Gadde Durga Prasad" });
  });
});
