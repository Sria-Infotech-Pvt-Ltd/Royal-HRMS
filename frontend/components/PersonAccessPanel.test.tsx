// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import PersonAccessPanel from "./PersonAccessPanel"

const row = { uuid: "u1", employee_id: "EMP1", full_name: "Aarav Nair", branch: "Mulugu", position: "Analyst", is_superuser: false, total: 3, from_baseline: 1, from_seat: 1, extra: 1 }
const setAccess = vi.fn()
vi.mock("@/hooks/useEmployeeAccessList", () => ({
  useEmployeeAccessList: () => ({
    list: { data: { count: 2, page: 1, total_pages: 1, results: [row, { ...row, uuid: "u2", employee_id: "EMP2", full_name: "Sria", is_superuser: true, position: "" }] }, loading: false, error: null },
    branchOptions: [], filters: { search: "", branch: "", access: "", page: 1 }, setSearch: vi.fn(), setBranch: vi.fn(), setAccess, setPage: vi.fn(),
  }),
}))
const saveExtra = vi.fn()
// Stable objects, like the real hook returns: a fresh object on every render would re-run the panel's effect forever.
const personAccess = { employee: "u1", employee_id: "EMP1", full_name: "Aarav Nair", baseline: ["leave.view"], seat: { title: "Analyst", codenames: ["payroll.view"] }, extra: ["leave.create"] }
vi.mock("@/hooks/usePersonAccess", () => ({
  usePersonAccess: (uuid: string | null) => ({ access: uuid ? personAccess : null, loading: false, error: null, isSaving: false, saveError: null, saveExtra }),
}))

const item = (codename: string) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive: false })
const catalogue = {
  leave: [item("leave.view"), item("leave.create"), item("leave.approve")],
  payroll: [item("payroll.view"), item("payroll.export")],
  settings: [item("settings.edit")],
}

beforeEach(() => { saveExtra.mockReset().mockResolvedValue(true); setAccess.mockReset() })
afterEach(() => cleanup())

function openPerson() {
  render(<PersonAccessPanel catalogue={catalogue} canEdit />)
  fireEvent.click(screen.getAllByRole("button", { name: /Manage access/ })[0])
}

describe("employee list", () => {
  it("shows people with initials, marks a missing position and a superuser, and filters by chip", () => {
    render(<PersonAccessPanel catalogue={catalogue} canEdit />)
    expect(screen.getByText("AN")).toBeTruthy()
    expect(screen.getByText("Superuser")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /Has extra access/ }))
    expect(setAccess).toHaveBeenCalledWith("extra")
  })
})

describe("one person", () => {
  it("shows where each permission comes from and locks what is already held", () => {
    openPerson()
    const leaveView = screen.getAllByRole("checkbox", { name: "view" })[0] as HTMLButtonElement
    expect(leaveView.disabled).toBe(true)                      // from everyone
    expect(screen.getByText("(everyone)")).toBeTruthy()
    expect(screen.getByText("(their seat)")).toBeTruthy()
    expect(screen.queryByText(/settings/i)).toBeNull()         // full access is never a per-person tick
  })

  it("counts unsaved changes, adds a whole module, discards, and saves the chosen extras", async () => {
    openPerson()
    expect(screen.queryByText(/unsaved change/)).toBeNull()
    fireEvent.click(screen.getByRole("checkbox", { name: "approve" }))
    expect(screen.getByText(/1 unsaved change/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Discard" }))
    expect(screen.queryByText(/unsaved change/)).toBeNull()

    fireEvent.click(screen.getByRole("button", { name: /Add all 1/ }))      // payroll: only "export" is still addable
    fireEvent.click(screen.getByRole("checkbox", { name: "approve" }))
    expect(screen.getByText(/2 unsaved changes/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /Save access/ }))
    await waitFor(() => expect(saveExtra).toHaveBeenCalled())
    expect([...saveExtra.mock.calls[0][0]].sort()).toEqual(["leave.approve", "leave.create", "payroll.export"])
  })

  it("narrows the modules by view and search", () => {
    openPerson()
    fireEvent.click(screen.getByRole("button", { name: /Extra selected/ }))
    expect(screen.getByText("Showing 1 of 2 modules")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /All modules/ }))
    fireEvent.change(screen.getByLabelText("Search permissions"), { target: { value: "payroll" } })
    expect(screen.getByText("Showing 1 of 1 modules")).toBeTruthy()
  })
})
