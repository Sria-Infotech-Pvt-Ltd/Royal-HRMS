// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import PerformanceHeader from "./_components/PerformanceHeader"
import StageFunnel from "./_components/StageFunnel"
import CyclesTab from "./_components/CyclesTab"
import type { ApiCycle } from "@/types/performanceHub"

afterEach(cleanup)

const cycle = (over: Partial<ApiCycle> = {}): ApiCycle => ({
  id: "c1", name: "Q4 2026", period_start: "2026-10-01", period_end: "2026-12-31", self_review_due: "2026-11-15", manager_review_due: "2026-12-01", status: "draft", ...over,
})
const today = new Date(2026, 10, 10)

describe("the hub's header and tabs", () => {
  const props = { tab: "overview" as const, onTab: vi.fn(), onBack: vi.fn(), needsHrCount: 3, cycleCount: 2 }

  it("offers a Back button and calls it", () => {
    const onBack = vi.fn()
    render(<PerformanceHeader {...props} onBack={onBack} />)
    fireEvent.click(screen.getByRole("button", { name: /Back/ }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })

  it("has no New review cycle button at the top", () => {
    render(<PerformanceHeader {...props} />)
    expect(screen.queryByRole("button", { name: /New review cycle/ })).toBeNull()
  })

  it("has the three sections, marks the open one, and switches when one is clicked", () => {
    const onTab = vi.fn()
    render(<PerformanceHeader {...props} onTab={onTab} />)
    expect(screen.getAllByRole("tab")).toHaveLength(3)
    expect(screen.getByRole("tab", { name: /Overview/ }).getAttribute("aria-selected")).toBe("true")
    fireEvent.click(screen.getByRole("tab", { name: /Review queue/ }))
    expect(onTab).toHaveBeenCalledWith("queue")
  })

  it("shows how many reviews wait for HR on the queue tab", () => {
    render(<PerformanceHeader {...props} />)
    expect(screen.getByRole("tab", { name: /Review queue/ }).textContent).toContain("3")
  })
})

describe("the review funnel", () => {
  const counts = { not_started: 4, awaiting_manager: 0, awaiting_calibration: 2, awaiting_publish: 0, published: 0, acknowledged: 1, total: 7 }

  it("opens exactly the reviews at a step when that step is clicked", () => {
    const onSelect = vi.fn()
    render(<StageFunnel counts={counts} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole("button", { name: /To calibrate/ }))
    expect(onSelect).toHaveBeenCalledWith("awaiting_calibration")
  })

  it("does not let you open a step with nobody in it", () => {
    render(<StageFunnel counts={counts} onSelect={vi.fn()} />)
    expect((screen.getByRole("button", { name: /With manager/ }) as HTMLButtonElement).disabled).toBe(true)
  })

  it("says so when there are no reviews", () => {
    render(<StageFunnel counts={{ ...counts, total: 0 }} onSelect={vi.fn()} />)
    expect(screen.getByText(/No reviews yet/)).toBeTruthy()
  })
})

describe("the cycles tab", () => {
  const base = { today, isLoading: false, busyId: null, error: "", onDismissError: vi.fn(), onCreate: vi.fn(), onActivate: vi.fn(), onClose: vi.fn() }

  it("activates a draft cycle", () => {
    const onActivate = vi.fn()
    render(<CyclesTab {...base} cycles={[cycle()]} onActivate={onActivate} />)
    fireEvent.click(screen.getByRole("button", { name: /Activate/ }))
    expect(onActivate).toHaveBeenCalledWith("c1")
  })

  it("closes an active cycle, and offers nothing for a closed one", () => {
    const onClose = vi.fn()
    const { unmount } = render(<CyclesTab {...base} cycles={[cycle({ status: "active" })]} onClose={onClose} />)
    fireEvent.click(screen.getByRole("button", { name: /Close cycle/ }))
    expect(onClose).toHaveBeenCalledWith("c1")
    unmount()
    render(<CyclesTab {...base} cycles={[cycle({ status: "closed" })]} />)
    expect(screen.queryByRole("button", { name: /Activate|Close cycle/ })).toBeNull()
    expect(screen.getByText(/cannot be reopened/)).toBeTruthy()
  })

  it("lists the active cycle before drafts and closed ones", () => {
    render(<CyclesTab {...base} cycles={[cycle({ id: "a", name: "Closed one", status: "closed" }), cycle({ id: "b", name: "Draft one" }), cycle({ id: "c", name: "Active one", status: "active" })]} />)
    const names = screen.getAllByRole("heading", { level: 3 }).map(node => node.textContent)
    expect(names).toEqual(["Active one", "Draft one", "Closed one"])
  })

  it("shows the reason a change was refused", () => {
    render(<CyclesTab {...base} cycles={[cycle()]} error={'"Q3" is already active — close it first.'} />)
    expect(screen.getByText(/already active/)).toBeTruthy()
  })

  it("invites you to create the first cycle", () => {
    const onCreate = vi.fn()
    render(<CyclesTab {...base} cycles={[]} onCreate={onCreate} />)
    fireEvent.click(screen.getByRole("button", { name: /New review cycle/ }))
    expect(onCreate).toHaveBeenCalledTimes(1)
  })
})
