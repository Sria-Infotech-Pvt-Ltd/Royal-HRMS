// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import FamilyMemberCard from "./FamilyMemberCard"
import type { FamilyEntry } from "./familyNominationTypes"

afterEach(cleanup)

const entry = (over: Partial<FamilyEntry> = {}): FamilyEntry => ({ id: "f1", name: "Ravi", relationship: "father", date_of_birth: "", gender: "male", blood_group: "", is_dependent: false, ...over })
const mount = (over: Partial<FamilyEntry> = {}, handlers: { onChange?: () => void; onRemove?: () => void } = {}) =>
  render(<FamilyMemberCard entry={entry(over)} isOpen isNominee={false} roleNote={null} onToggle={vi.fn()} onChange={handlers.onChange ?? vi.fn()} onRemove={handlers.onRemove ?? vi.fn()} />)

describe("Dependent on the employee", () => {
  it("is a Yes / No choice in a row of its own, not a loose checkbox beside another field", () => {
    mount()
    expect(screen.getByText("Dependent on the employee")).toBeTruthy()
    expect(screen.getByRole("group", { name: "Dependent on the employee" })).toBeTruthy()
    expect(screen.queryByRole("checkbox")).toBeNull()
    expect(screen.getByRole("button", { name: "No" }).getAttribute("aria-pressed")).toBe("true")
    expect(screen.getByRole("button", { name: "Yes" }).getAttribute("aria-pressed")).toBe("false")
  })

  it("says Yes when the person is a dependant", () => {
    mount({ is_dependent: true })
    expect(screen.getByRole("button", { name: "Yes" }).getAttribute("aria-pressed")).toBe("true")
  })

  it("reports the choice", () => {
    const onChange = vi.fn()
    mount({}, { onChange })
    fireEvent.click(screen.getByRole("button", { name: "Yes" }))
    expect(onChange).toHaveBeenCalledWith("is_dependent", true)
    fireEvent.click(screen.getByRole("button", { name: "No" }))
    expect(onChange).toHaveBeenCalledWith("is_dependent", false)
  })
})

describe("the delete button", () => {
  it("is red, so it reads as the destructive action", () => {
    mount()
    expect(screen.getByRole("button", { name: "Remove Ravi" }).style.color).toContain("--crit")
  })

  it("removes the member when clicked", () => {
    const onRemove = vi.fn()
    mount({}, { onRemove })
    fireEvent.click(screen.getByRole("button", { name: "Remove Ravi" }))
    expect(onRemove).toHaveBeenCalledTimes(1)
  })
})
