import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactElement, ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Server-render (no DOM) like the other component tests in this repo; useFetch
// is mocked per URL so each component renders its loaded state.
const fetched: Record<string, unknown> = {};
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    const key = url ? Object.keys(fetched).find(k => url.startsWith(k)) : undefined;
    return { data: key ? fetched[key] : null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));

import ApproversSection from "./ApproversSection";
import DeleteContactModal from "./DeleteContactModal";

const APPROVERS = "/company-contacts/approvers/";
const WORKFLOWS = [
  { value: "leave", label: "Leave Request" }, { value: "expense", label: "Expense Claim" },
  { value: "attendance_correction", label: "Attendance Correction" }, { value: "wfh", label: "Work From Home Request" },
];
const mgr = { name: "Mona Manager", email: "mona@example.com", phone: "9000000001" };
const hr  = { name: "Hari HR", email: "hari@example.com", phone: "" };
const row = (employee_id: string, name: string, l1: typeof mgr | null, l2: typeof mgr | null) => ({
  employee_id, name, department: "Ops", branch: "Surat", l1, l2,
});

beforeEach(() => {
  for (const k of Object.keys(fetched)) delete fetched[k];
});

describe("DeleteContactModal", () => {
  // Walk the returned element to the footer buttons and call their handlers.
  function buttons(onCancel = vi.fn(), onConfirm = vi.fn(), deleting = false) {
    const modal = DeleteContactModal({ name: "Surat HR", deleting, onCancel, onConfirm }) as ReactElement<{ footer: ReactElement<{ children: ReactElement<{ onClick: () => void; disabled: boolean; children: ReactNode }>[] }> }>;
    const [cancel, del] = modal.props.footer.props.children;
    return { cancel, del, onCancel, onConfirm };
  }

  it("names the contact and offers Cancel and Delete", () => {
    const html = renderToStaticMarkup(
      <DeleteContactModal name="Surat HR" deleting={false} onCancel={() => {}} onConfirm={() => {}} />);
    expect(html).toContain("Remove <strong>Surat HR</strong> from the Contact Matrix?");
    expect(html).toContain(">Cancel<");
    expect(html).toContain(">Delete<");
  });

  it("Cancel closes without deleting", () => {
    const { cancel, onCancel, onConfirm } = buttons();
    cancel.props.onClick();
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("deletes only when Delete is clicked", () => {
    const { del, onCancel, onConfirm } = buttons();
    expect(onConfirm).not.toHaveBeenCalled();
    del.props.onClick();
    expect(onConfirm).toHaveBeenCalledOnce();
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("locks both buttons while deleting", () => {
    const { cancel, del } = buttons(vi.fn(), vi.fn(), true);
    expect(cancel.props.disabled).toBe(true);
    expect(del.props.disabled).toBe(true);
    expect(del.props.children).toBe("Deleting…");
  });
});

describe("ApproversSection", () => {
  it("shows my L1 / L2 with email and phone, and Not Assigned when missing", () => {
    fetched[APPROVERS] = { workflow: "leave", workflows: WORKFLOWS, me: row("E1", "Me", mgr, null), team: null };
    const html = renderToStaticMarkup(<ApproversSection />);
    expect(html).toContain("My Approvers");
    expect(html).toContain("Mona Manager");
    expect(html).toContain('href="mailto:mona@example.com"');
    expect(html).toContain('href="tel:9000000001"');
    expect(html).toContain("Not Assigned");
    expect(html).toContain("Work From Home Request");
  });

  it("hides the team table without employees.view (team = null)", () => {
    fetched[APPROVERS] = { workflow: "leave", workflows: WORKFLOWS, me: row("E1", "Me", null, null), team: null };
    expect(renderToStaticMarkup(<ApproversSection />)).not.toContain("Employee Approvers");
  });

  it("lists the team with both, only L1, only L2 and no approvers", () => {
    fetched[APPROVERS] = {
      workflow: "leave", workflows: WORKFLOWS, me: row("HR1", "Me", null, null),
      team: [row("E1", "Both", mgr, hr), row("E2", "OnlyL1", mgr, null), row("E3", "OnlyL2", null, hr),
             row("E4", "Nobody", null, null)],
    };
    const html = renderToStaticMarkup(<ApproversSection />);
    expect(html).toContain("Employee Approvers");
    for (const name of ["Both", "OnlyL1", "OnlyL2", "Nobody"]) expect(html).toContain(name);
    expect(html).toContain("No phone");                        // Hari HR has no phone
    expect(html.match(/Not Assigned/g)?.length).toBe(2 + 1 + 1 + 2);   // me ×2, E2 L2, E3 L1, E4 ×2
  });

  it("explains an empty scope", () => {
    fetched[APPROVERS] = { workflow: "leave", workflows: WORKFLOWS, me: row("M1", "Me", null, null), team: [] };
    expect(renderToStaticMarkup(<ApproversSection />)).toContain("No employees in your scope.");
  });

  it("defaults to Leave and shows no Expense note", () => {
    fetched[APPROVERS] = { workflow: "leave", workflows: WORKFLOWS, me: row("E1", "Me", null, null), team: null };
    const html = renderToStaticMarkup(<ApproversSection />);
    expect(html).toMatch(/<option value="leave" selected="">Leave Request<\/option>/);
    expect(html).not.toContain("Expense claims are approved in one step");
  });
});
