// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({ rules: [] as Array<Record<string, unknown>>, loading: false, error: null as string | null }));
const patch = vi.hoisted(() => vi.fn());
const push = vi.hoisted(() => vi.fn());
const refetch = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/lib/clientApi", () => ({ default: { patch } }));
vi.mock("@/lib/api/endpoints", () => ({ API: { settings: { approvalRules: "/settings/approval-rules/" } } }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: mock.loading ? null : mock.rules, loading: mock.loading, error: mock.error, refetch }) }));
vi.mock("@/components/SearchableSelect", () => ({
  default: ({ value, onChange, options, placeholder }: { value: string; onChange: (value: string) => void; options: { value: string; label: string }[]; placeholder?: string }) => (
    <select aria-label={placeholder} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">{placeholder}</option>
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  ),
}));

import { flowSteps, initialsOf, summarise } from "./_components/approvalFlowView";
import ApprovalRulesPage from "./page";

const RULE = (type: string, label: string, overrides: Record<string, unknown> = {}) => ({
  workflow_type: type, workflow_label: label, l1_approver_kind: "reporting_manager", l1_approver_label: "Reporting manager", l1_approver_user_id: null,
  l2_approver_kind: "hr", l2_approver_label: "HR partner", l2_approver_user_id: null,
  eligible_approvers: [{ id: "u1", employee_id: "EMP001", full_name: "Asha Rao", department: "Sales" }], ...overrides,
});

beforeEach(() => {
  mock.rules = [RULE("leave", "Leave Request"), RULE("expense", "Expense Claim", { l2_approver_kind: "", l2_approver_label: "" }), RULE("attendance_correction", "Attendance Correction")];
  mock.loading = false; mock.error = null; patch.mockReset(); push.mockReset(); refetch.mockReset(); patch.mockResolvedValue({});
});
afterEach(cleanup);

const list = () => within(screen.getByRole("region", { name: "Approval workflows" }));
const editor = (label: string) => within(screen.getByRole("region", { name: `Edit ${label}` }));

describe("approval flow helpers", () => {
  it("draws submitted, level 1, level 2 and approved, and drops level 2 when there is none", () => {
    expect(flowSteps({ kind: "reporting_manager", label: "Reporting manager" }, { kind: "hr", label: "HR partner" }).map(step => step.key)).toEqual(["submit", "l1", "l2", "done"]);
    const single = flowSteps({ kind: "hr", label: "HR partner" }, { kind: "", label: "" });
    expect(single.map(step => step.key)).toEqual(["submit", "l1", "done"]);
    expect(single[2].detail).toBe("After level 1");
  });
  it("marks a missing level 1 instead of hiding it", () => {
    expect(flowSteps({ kind: "", label: "" }, { kind: "", label: "" })[1]).toMatchObject({ detail: "Not set", isMissing: true });
  });
  it("counts the workflows, the levels and the named people", () => {
    expect(summarise(mock.rules as never)).toEqual({ workflows: 3, twoLevel: 2, oneLevel: 1, namedPeople: 0, unset: 0 });
  });
  it("makes initials from a person's label", () => {
    expect(initialsOf("Asha Rao (EMP001) — Sales")).toBe("AR");
    expect(initialsOf("")).toBe("?");
  });
});

describe("the Approval Rules page", () => {
  it("shows the totals and each workflow with its flow drawn out, and a link to the change history", () => {
    render(<ApprovalRulesPage />);
    expect(screen.getByLabelText("Summary").textContent).toContain("3 workflows · 2 two-level · 1 single-level");
    const flows = list().getAllByRole("list", { name: "Approval flow" });
    expect(flows).toHaveLength(3);
    expect(within(flows[0]).getAllByRole("listitem")).toHaveLength(4);
    expect(within(flows[1]).getAllByRole("listitem")).toHaveLength(3);
    expect(screen.getByRole("link", { name: /Change history/ }).getAttribute("href")).toBe("/dashboard/settings/audit?module=settings");
  });

  it("warns when a workflow has no level 1 approver", () => {
    mock.rules = [RULE("leave", "Leave Request", { l1_approver_kind: "", l1_approver_label: "" })];
    render(<ApprovalRulesPage />);
    expect(screen.getByRole("alert").textContent).toContain("1 workflow has no level 1 approver");
  });

  it("opens the editor inside the row, shows a live preview, and closes it again", () => {
    render(<ApprovalRulesPage />);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(list().getByRole("button", { name: "Edit Expense Claim" }));
    const open = editor("Expense Claim");
    expect((open.getByLabelText("— Select who approves —") as HTMLSelectElement).value).toBe("reporting_manager");
    expect(open.getAllByRole("listitem")).toHaveLength(3);
    fireEvent.change(open.getByLabelText("— Single level (no L2) —"), { target: { value: "hr" } });
    expect(open.getAllByRole("listitem")).toHaveLength(4);
    expect(patch).not.toHaveBeenCalled();
    fireEvent.click(list().getByRole("button", { name: "Edit Expense Claim" }));
    expect(screen.queryByRole("region", { name: "Edit Expense Claim" })).toBeNull();
  });

  it("shows a named person's initials, and can remove level 2", () => {
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    const open = editor("Leave Request");
    fireEvent.change(open.getByLabelText("— Select who approves —"), { target: { value: "person:u1" } });
    expect(open.getByText("AR")).toBeTruthy();
    fireEvent.click(open.getByRole("button", { name: /Remove level 2/ }));
    expect(open.getAllByRole("listitem")).toHaveLength(3);
  });

  it("will not save without a level 1 approver", () => {
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    const open = editor("Leave Request");
    fireEvent.change(open.getByLabelText("— Select who approves —"), { target: { value: "" } });
    expect(open.getByText("Pick who approves first. Level 1 is required.")).toBeTruthy();
    expect((open.getByRole("button", { name: "Save Rule" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("saves one workflow with the same request as before, closes the editor, and offers Undo", async () => {
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    const open = editor("Leave Request");
    fireEvent.change(open.getByLabelText("— Select who approves —"), { target: { value: "person:u1" } });
    fireEvent.change(open.getByLabelText("— Single level (no L2) —"), { target: { value: "" } });
    fireEvent.click(open.getByRole("button", { name: "Save Rule" }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/settings/approval-rules/", { workflow_type: "leave", l1_approver_kind: "person", l1_approver_user: "u1", l2_approver_kind: "", l2_approver_user: null }));
    await waitFor(() => expect(screen.queryByRole("region", { name: "Edit Leave Request" })).toBeNull());
    expect(refetch).toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toContain("Saved for Leave Request.");
  });

  it("undoes the last save by putting the old approvers back", async () => {
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    fireEvent.change(editor("Leave Request").getByLabelText("— Select who approves —"), { target: { value: "hr" } });
    fireEvent.click(editor("Leave Request").getByRole("button", { name: "Save Rule" }));
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    patch.mockClear();
    fireEvent.click(screen.getByRole("button", { name: /Undo/ }));
    await waitFor(() => expect(patch).toHaveBeenCalledWith("/settings/approval-rules/", { workflow_type: "leave", l1_approver_kind: "reporting_manager", l1_approver_user: null, l2_approver_kind: "hr", l2_approver_user: null }));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("applies the same approvers to every workflow when asked", async () => {
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    const open = editor("Leave Request");
    fireEvent.change(open.getByLabelText("— Select who approves —"), { target: { value: "hr" } });
    fireEvent.click(open.getByRole("checkbox", { name: /Apply these approvers to all 3 workflows/ }));
    fireEvent.click(open.getByRole("button", { name: "Save to all" }));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(3));
    expect(patch.mock.calls.map(call => (call[1] as { workflow_type: string }).workflow_type)).toEqual(["leave", "expense", "attendance_correction"]);
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Leave Request, Expense Claim, Attendance Correction"));
  });

  it("names the workflow the server refused when applying to all, and keeps the editor open", async () => {
    patch.mockImplementation((_url: string, body: { workflow_type: string }) => body.workflow_type === "expense" ? Promise.reject({ response: { data: { message: "Not allowed to approve expenses." } } }) : Promise.resolve({}));
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    const open = editor("Leave Request");
    fireEvent.click(open.getByRole("checkbox"));
    fireEvent.click(open.getByRole("button", { name: "Save to all" }));
    await waitFor(() => expect(open.getByRole("alert").textContent).toContain("Expense Claim: Not allowed to approve expenses."));
    expect(screen.getByRole("status").textContent).toContain("Leave Request, Attendance Correction");
  });

  it("shows the server's message when a single save fails, and keeps the editor open", async () => {
    patch.mockRejectedValue({ response: { data: { message: "Approver cannot approve their own request." } } });
    render(<ApprovalRulesPage />);
    fireEvent.click(list().getByRole("button", { name: "Edit Leave Request" }));
    fireEvent.click(editor("Leave Request").getByRole("button", { name: "Save Rule" }));
    await waitFor(() => expect(editor("Leave Request").getByRole("alert").textContent).toContain("Approver cannot approve their own request."));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("shows placeholders while loading, an empty state, an error, and goes back", () => {
    mock.loading = true;
    render(<ApprovalRulesPage />);
    expect(list().getAllByLabelText("Loading")).toHaveLength(3);
    cleanup();
    mock.loading = false; mock.rules = [];
    render(<ApprovalRulesPage />);
    expect(list().getByText("No approval workflows found.")).toBeTruthy();
    cleanup();
    mock.error = "Could not load";
    render(<ApprovalRulesPage />);
    expect(screen.getByRole("alert").textContent).toContain("Could not load");
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(push).toHaveBeenCalledWith("/dashboard/settings");
  });
});
