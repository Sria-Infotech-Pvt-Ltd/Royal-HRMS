// @vitest-environment jsdom
// Opening an employee code that does not exist used to show "Viewing this employee's workspace" above an empty page.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const fetched = vi.hoisted(() => ({ state: { data: null as { full_name: string; employee_id: string } | null, error: null as string | null } }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ ...fetched.state, loading: false, status: null, refetch: () => undefined }) }));
vi.mock("next/link", () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }));

import ViewAsStrip from "./ViewAsStrip";

afterEach(() => cleanup());

describe("ViewAsStrip", () => {
  it("names the employee being viewed", () => {
    fetched.state = { data: { full_name: "Asha Rao", employee_id: "QA0003" }, error: null };
    render(<ViewAsStrip />);
    expect(screen.getByText(/Viewing Asha Rao's workspace — read-only/)).toBeTruthy();
  });

  it("says plainly when the employee cannot be found, with what to do next", () => {
    fetched.state = { data: null, error: "Unknown employee." };
    render(<ViewAsStrip />);
    expect(screen.getByText(/Unknown employee\. Check the employee ID, then go back to Employees\./)).toBeTruthy();
    expect(screen.queryByText(/Viewing this employee's workspace/)).toBeNull();
  });
});
