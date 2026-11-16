// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import WfhAddressSearch from "./WfhAddressSearch"

const searchAddress = vi.fn()
vi.mock("@/lib/geocode", () => ({ searchAddress: (...args: unknown[]) => searchAddress(...args) }))

const placeholder = "House / street, area, city, pincode"

beforeEach(() => searchAddress.mockReset())
afterEach(() => cleanup())

describe("WfhAddressSearch", () => {
  it("does not search while typing, and refuses a query under 4 characters", () => {
    render(<WfhAddressSearch inputClassName="x" onPick={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value: "ab" } })
    expect(searchAddress).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Search" }))
    expect(screen.getByRole("alert").textContent).toContain("Type at least the street, area and city.")
    expect(searchAddress).not.toHaveBeenCalled()
  })

  it("lists matches and reports the picked one", async () => {
    searchAddress.mockResolvedValue([{ label: "Road A, City", latitude: 17.38, longitude: 78.48 }])
    const onPick = vi.fn()
    render(<WfhAddressSearch inputClassName="x" onPick={onPick} />)
    fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value: "Road A City" } })
    fireEvent.click(screen.getByRole("button", { name: "Search" }))
    const option = await screen.findByRole("option", { name: "Road A, City" })
    expect(option.getAttribute("aria-selected")).toBe("false")
    fireEvent.click(option)
    expect(onPick).toHaveBeenCalledWith({ label: "Road A, City", latitude: 17.38, longitude: 78.48 })
    expect(screen.getByRole("option", { name: "Road A, City" }).getAttribute("aria-selected")).toBe("true")
  })

  it("says so when nothing matches, and shows the error when the search fails", async () => {
    searchAddress.mockResolvedValueOnce([])
    render(<WfhAddressSearch inputClassName="x" onPick={vi.fn()} />)
    fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value: "Nowhere at all" } })
    fireEvent.click(screen.getByRole("button", { name: "Search" }))
    expect(await screen.findByText("No match found. Try adding the area, city or pincode.")).toBeTruthy()
    searchAddress.mockRejectedValueOnce(new Error("The address search is unavailable right now."))
    fireEvent.click(screen.getByRole("button", { name: "Search" }))
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("unavailable"))
  })
})
