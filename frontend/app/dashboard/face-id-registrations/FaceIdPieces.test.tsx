// @vitest-environment jsdom
import { createRef } from "react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import EmployeeFaceCard from "./_components/EmployeeFaceCard"
import EmployeePickerPanel from "./_components/EmployeePickerPanel"
import FaceCoverageCard from "./_components/FaceCoverageCard"
import type { FaceRegistrationEmployee } from "@/types/faceRegistration"

afterEach(cleanup)

const employee = (status: FaceRegistrationEmployee["face_status"] = "none"): FaceRegistrationEmployee => ({
  uuid: "u1", employee_id: "EMP1", full_name: "Asha Verma", email: "a@example.com", branch: "Hyd", department: "Eng", designation: "Dev", face_status: status,
})
const handlers = { onRegister: vi.fn(), onConfirm: vi.fn(), onCancelConfirm: vi.fn() }

describe("the three steps shown before an employee is chosen", () => {
  it("shows all three steps", () => {
    render(<EmployeeFaceCard employee={null} status={undefined} isLoading={false} error={null} isConfirming={false} onStart={vi.fn()} {...handlers} />)
    for (const name of ["Pick an employee", "Get their consent", "Capture the face"]) expect(screen.getByText(name)).toBeTruthy()
  })

  it("takes you to the employee search when you click step 1", () => {
    const onStart = vi.fn()
    render(<EmployeeFaceCard employee={null} status={undefined} isLoading={false} error={null} isConfirming={false} onStart={onStart} {...handlers} />)
    fireEvent.click(screen.getByRole("button", { name: /Step 1: Pick an employee/ }))
    expect(onStart).toHaveBeenCalledTimes(1)
  })

  it("marks steps 2 and 3 as locked until someone is chosen, and sends you back to step 1 if you click them", () => {
    const onStart = vi.fn()
    render(<EmployeeFaceCard employee={null} status={undefined} isLoading={false} error={null} isConfirming={false} onStart={onStart} {...handlers} />)
    const locked = screen.getAllByRole("button", { name: /Locked until an employee is chosen/ })
    expect(locked).toHaveLength(2)
    fireEvent.click(locked[0])
    expect(onStart).toHaveBeenCalledTimes(1)
  })

  it("shows the profile instead of the steps once an employee is chosen", () => {
    render(<EmployeeFaceCard employee={employee()} status={undefined} isLoading={false} error={null} isConfirming={false} onStart={vi.fn()} {...handlers} />)
    expect(screen.queryByText("Pick an employee")).toBeNull()
    expect(screen.getByRole("button", { name: /Register Face ID/ })).toBeTruthy()
  })
})

describe("the search box can be focused from outside (step 1)", () => {
  it("hands its input to the ref it is given", () => {
    const ref = createRef<HTMLInputElement>()
    render(<EmployeePickerPanel search="" onSearch={vi.fn()} employees={[]} total={0} page={1} pageSize={20} totalPages={1} onPage={vi.fn()} isLoading={false} error={null} selectedId={null} onSelect={vi.fn()} filter="" searchRef={ref} />)
    expect(ref.current).toBe(screen.getByLabelText(/Search employees/))
    ref.current?.focus()
    expect(document.activeElement).toBe(ref.current)
  })
})

describe("the employee list shows who has not completed registration", () => {
  it("shows each person's Face ID status on their row", () => {
    const rows = [employee("approved"), { ...employee("pending"), uuid: "u2", full_name: "Ravi Kumar" }, { ...employee("none"), uuid: "u3", full_name: "Meena Iyer" }]
    render(<EmployeePickerPanel search="" onSearch={vi.fn()} employees={rows} total={3} page={1} pageSize={20} totalPages={1} onPage={vi.fn()} isLoading={false} error={null} selectedId={null} onSelect={vi.fn()} filter="" />)
    expect(screen.getByText("Approved")).toBeTruthy()
    expect(screen.getByText("Pending")).toBeTruthy()
    expect(screen.getByText("Not registered")).toBeTruthy()
  })

  it("congratulates instead of showing a blank list when everyone is registered", () => {
    render(<EmployeePickerPanel search="" onSearch={vi.fn()} employees={[]} total={0} page={1} pageSize={20} totalPages={1} onPage={vi.fn()} isLoading={false} error={null} selectedId={null} onSelect={vi.fn()} filter="incomplete" />)
    expect(screen.getByText("Everyone is registered")).toBeTruthy()
  })

  it("lists the not-completed people when you click the button on the coverage card", () => {
    const onFilter = vi.fn()
    render(<FaceCoverageCard counts={{ total: 50, approved: 37, pending: 4, rejected: 2, none: 7, incomplete: 13 }} isLoading={false} filter="" onFilter={onFilter} />)
    fireEvent.click(screen.getByRole("button", { name: /Show 13 not completed/ }))
    expect(onFilter).toHaveBeenCalledWith("incomplete")
  })

  it("clears the filter when you click the one that is already on", () => {
    const onFilter = vi.fn()
    render(<FaceCoverageCard counts={{ total: 50, approved: 37, pending: 4, rejected: 2, none: 7, incomplete: 13 }} isLoading={false} filter="incomplete" onFilter={onFilter} />)
    fireEvent.click(screen.getByRole("button", { name: /Show 13 not completed/ }))
    expect(onFilter).toHaveBeenCalledWith("")
  })

  it("filters by one status from the legend", () => {
    const onFilter = vi.fn()
    render(<FaceCoverageCard counts={{ total: 50, approved: 37, pending: 4, rejected: 2, none: 7, incomplete: 13 }} isLoading={false} filter="" onFilter={onFilter} />)
    fireEvent.click(screen.getByRole("button", { name: /Not registered/ }))
    expect(onFilter).toHaveBeenCalledWith("none")
  })

  it("has nothing to filter when everyone is registered", () => {
    render(<FaceCoverageCard counts={{ total: 5, approved: 5, pending: 0, rejected: 0, none: 0, incomplete: 0 }} isLoading={false} filter="" onFilter={vi.fn()} />)
    expect((screen.getByRole("button", { name: /Everyone is registered/ }) as HTMLButtonElement).disabled).toBe(true)
  })
})
