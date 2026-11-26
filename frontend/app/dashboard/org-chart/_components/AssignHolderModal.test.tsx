// @vitest-environment jsdom
// The holder picker must send the employee's database id: the placement API looks the person up by it, and sending the
// employee code (e.g. 10000002) came back as 404 "Employee not found".
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Position } from "@/types/orgStructure";

const post = vi.hoisted(() => vi.fn(() => Promise.resolve({ data: {} })));
vi.mock("@/lib/clientApi", () => ({ default: { post } }));
vi.mock("@/components/SearchableSelect", () => ({
  default: ({ options, onChange }: { options: { value: string; label: string }[]; onChange: (value: string) => void }) => (
    <select aria-label="employee" onChange={event => onChange(event.target.value)}>
      <option value="" />
      {options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
    </select>
  ),
}));

import AssignHolderModal from "./AssignHolderModal";

afterEach(cleanup);

describe("AssignHolderModal", () => {
  it("sends the chosen employee's database id, not their employee code", async () => {
    const position = { id: "pos-1", title: "Analyst", org_unit_name: "Unit", holder: null } as unknown as Position;   // only these fields are read
    const onAssigned = vi.fn();
    render(
      <AssignHolderModal
        position={position}
        employees={[{ id: "10000002", uuid: "3ba8599b-ff6f-4372-aad1-acc6ab8f0dd3", full_name: "Asha Rao", employee_id: "10000002" }]}
        onClose={() => {}} onAssigned={onAssigned}
      />,
    );
    fireEvent.change(screen.getByLabelText("employee"), { target: { value: "3ba8599b-ff6f-4372-aad1-acc6ab8f0dd3" } });
    const submit = screen.getAllByRole("button").find(button => /assign/i.test(button.textContent ?? ""));
    if (!submit) throw new Error("no Assign button");
    fireEvent.click(submit);
    await vi.waitFor(() => expect(onAssigned).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(expect.any(String), expect.objectContaining({ employee: "3ba8599b-ff6f-4372-aad1-acc6ab8f0dd3" }));
  });
});
