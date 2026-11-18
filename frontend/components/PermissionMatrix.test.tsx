// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { useState } from "react"
import PermissionMatrix from "./PermissionMatrix"

const item = (codename: string, is_sensitive = false) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive })
const modules: [string, ReturnType<typeof item>[]][] = [
  ["leave", [item("leave.view"), item("leave.create"), item("leave.view_own")]],
  ["payroll", [item("payroll.view"), item("payroll.export", true)]],
]

function Harness({ start = [], isAdvanced = true, locked = [] }: { start?: string[]; isAdvanced?: boolean; locked?: string[] }) {
  const [granted, setGranted] = useState(new Set(start))
  return (
    <PermissionMatrix
      modules={modules} granted={granted} isAdvanced={isAdvanced} lockedCodenames={locked}
      onToggle={codename => setGranted(previous => { const next = new Set(previous); if (!next.delete(codename)) next.add(codename); return next })}
      onToggleMany={(codenames, isOn) => setGranted(previous => { const next = new Set(previous); codenames.forEach(codename => (isOn ? next.add(codename) : next.delete(codename))); return next })}
    />
  )
}

afterEach(() => cleanup())
const box = (name: RegExp | string) => screen.getByRole("checkbox", { name }) as HTMLInputElement

describe("PermissionMatrix (advanced)", () => {
  it("a column header switches that action for every module shown, with a dash while only some are on", () => {
    render(<Harness start={["leave.view"]} />)
    const header = box(/Switch every view permission/)
    expect(header.indeterminate).toBe(true)
    fireEvent.click(header)
    expect(box("leave view").checked).toBe(true)
    expect(box("payroll view").checked).toBe(true)
    expect(box(/Switch every view permission/).indeterminate).toBe(false)
    fireEvent.click(box(/Switch every view permission/))
    expect(box("leave view").checked).toBe(false)
    expect(box("payroll view").checked).toBe(false)
  })

  it("a column header does not touch locked permissions", () => {
    render(<Harness locked={["payroll.view"]} />)
    fireEvent.click(box(/Switch every view permission/))
    expect(box("leave view").checked).toBe(true)
    expect(box("payroll view").checked).toBe(false)
  })

  it("the row checkbox switches the whole module and shows a dash for a part", () => {
    render(<Harness start={["leave.view"]} />)
    expect(box("Select all leave permissions").indeterminate).toBe(true)
    fireEvent.click(box("Select all leave permissions"))
    expect(box("leave create").checked).toBe(true)
  })

  it("Other permissions are toggle chips", () => {
    render(<Harness />)
    const chip = screen.getByRole("checkbox", { name: /view own/i })
    expect(chip.getAttribute("aria-checked")).toBe("false")
    fireEvent.click(chip)
    expect(screen.getByRole("checkbox", { name: /view own/i }).getAttribute("aria-checked")).toBe("true")
  })

  it("search and filters narrow the modules shown, and say when nothing matches", () => {
    render(<Harness start={["payroll.view", "payroll.export"]} />)
    fireEvent.change(screen.getByLabelText("Search permissions"), { target: { value: "payroll" } })
    expect(screen.queryByLabelText("leave view")).toBeNull()
    expect(screen.getByLabelText("payroll view")).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Search permissions"), { target: { value: "" } })
    fireEvent.click(screen.getByRole("button", { name: /Off/ }))
    expect(screen.queryByLabelText("payroll view")).toBeNull()
    expect(screen.getByLabelText("leave view")).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Search permissions"), { target: { value: "zzz" } })
    expect(screen.getByText(/No module matches/)).toBeTruthy()
  })

  it("the plain matrix has no toolbar and no column checkboxes", () => {
    render(<Harness isAdvanced={false} />)
    expect(screen.queryByLabelText("Search permissions")).toBeNull()
    expect(screen.queryByLabelText(/Switch every view permission/)).toBeNull()
  })

  it("quick presets switch the modules shown, ask before Everything, and respect locked permissions", () => {
    render(<Harness start={["leave.create"]} locked={["payroll.export"]} />)
    fireEvent.click(screen.getByRole("button", { name: /View only/ }))
    expect(box("leave view").checked).toBe(true)
    expect(box("leave create").checked).toBe(false)
    expect(box("payroll view").checked).toBe(true)

    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    fireEvent.click(screen.getByRole("button", { name: /Everything/ }))
    expect(confirm).toHaveBeenCalled()
    expect(box("leave create").checked).toBe(false)   // declined: nothing changed
    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole("button", { name: /Everything/ }))
    expect(box("leave create").checked).toBe(true)
    expect(box("payroll export").checked).toBe(false)   // the locked one stayed off
    confirm.mockRestore()

    fireEvent.click(screen.getByRole("button", { name: /Nothing/ }))
    expect(box("leave view").checked).toBe(false)
  })

  it("a column header shows how many are on, and a read-only matrix has no presets", () => {
    render(<Harness start={["leave.view"]} />)
    expect(screen.getAllByText("1/2").length).toBeGreaterThan(0)
    cleanup()
    render(<PermissionMatrix modules={modules} granted={new Set()} onToggle={() => {}} onToggleMany={() => {}} isAdvanced isReadOnly />)
    expect(screen.queryByRole("button", { name: /View only/ })).toBeNull()
    expect(box(/Switch every view permission/).disabled).toBe(true)
  })
})
