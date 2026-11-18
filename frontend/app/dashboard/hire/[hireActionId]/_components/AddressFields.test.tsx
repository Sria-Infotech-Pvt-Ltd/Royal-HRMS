// @vitest-environment jsdom
import { useEffect, useState } from "react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react"
import { EMPTY_FORM } from "./_wizardData"
import type { PincodeLocation } from "@/hooks/usePincodeLookup"

// The REAL address section. Only the two lookups are stubs: the PIN-code answer, and the list of a district's PIN codes.
let lookupAnswer: PincodeLocation | null
const lookupSpy = vi.fn()
vi.mock("@/hooks/usePincodeLookup", () => ({
  usePincodeLookup: () => ({ lookup: (pincode: string) => { lookupSpy(pincode); return Promise.resolve(lookupAnswer) } }),
}))
const pinList = [{ pincode: "500001", area: "Hyderabad GPO" }, { pincode: "500081", area: "Cyberabad" }]
vi.mock("@/hooks/usePincodesInDistrict", () => ({
  usePincodesInDistrict: (state: string, district: string) => ({ options: state === "Telangana" && district === "Hyderabad" ? pinList : [], isLoading: false }),
}))

import AddressFields, { EMPTY_ADDRESS_EXTRAS } from "./AddressFields"

const held: { form: typeof EMPTY_FORM } = { form: EMPTY_FORM }
function Parent({ start }: { start?: Partial<typeof EMPTY_FORM> }) {
  // The permanent address is hidden while it is the same as the current one, so the current-address tests start that way.
  const [form, setForm] = useState({ ...EMPTY_FORM, permanent_same_as_current: "true", ...start })
  const [extras, setExtras] = useState(EMPTY_ADDRESS_EXTRAS)
  useEffect(() => { held.form = form })
  return <AddressFields form={form} extras={extras} onFieldChange={(key, value) => setForm(previous => ({ ...previous, [key]: value }))} onExtrasChange={(key, value) => setExtras(previous => ({ ...previous, [key]: value }))} />
}

const suggestButtons = () => screen.getAllByRole("button", { name: /Suggest/ })
/** The Suggest button inside the box with this label (State, District, City), in the nth address on the page. */
const suggestIn = (label: string, index = 0) => {
  const boxes = screen.getAllByText(label, { selector: "label" }).map(node => node.closest(".f") as HTMLElement)
  return within(boxes[index]).getByRole("button", { name: /Suggest/ })
}
const click = async (button: HTMLElement) => { await act(async () => { fireEvent.click(button) }) }

beforeEach(() => { lookupAnswer = { locality: "Cyberabad", district: "Hyderabad", state: "Telangana" }; lookupSpy.mockClear() })
afterEach(() => cleanup())

describe("Suggest buttons in the current address", () => {
  it("has one on State, District and City", () => {
    render(<Parent />)
    expect(suggestButtons()).toHaveLength(3)
  })

  it("says why when there is no PIN code yet, and changes nothing", async () => {
    render(<Parent />)
    for (const label of ["State", "District", "City"]) {
      await click(suggestIn(label))
      expect(screen.getByText(/Enter the 6-digit PIN code first/)).toBeTruthy()
    }
    expect(held.form.current_state).toBe("")
    expect(held.form.current_village).toBe("")
    expect(lookupSpy).not.toHaveBeenCalled()
  })

  it("fills the city from the PIN code", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await click(suggestIn("City"))
    expect(held.form.current_village).toBe("Cyberabad")
    expect(lookupSpy).toHaveBeenCalledWith("500081")
  })

  it("fills the state AND the district from the State button", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await click(suggestIn("State"))
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Hyderabad")
  })

  it("fills the state AND the district from the District button, so the district is not left in a locked, empty-looking box", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await click(suggestIn("District"))
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Hyderabad")
  })

  it("writes the state and district exactly as the server's PIN lookup spells them (the State / District lists use the same data)", async () => {
    lookupAnswer = { locality: "Jangaon", district: "Jangoan", state: "Telangana" }
    render(<Parent start={{ current_pin_code: "506167" }} />)
    await click(suggestIn("District"))
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Jangoan")
  })

  it("replaces a district that belongs to another state, because the PIN code decides", async () => {
    render(<Parent start={{ current_pin_code: "500081", current_state: "Karnataka", current_district: "Bengaluru Urban" }} />)
    await click(suggestIn("State"))
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Hyderabad")
  })

  it("says so when the PIN code is not known", async () => {
    lookupAnswer = null
    render(<Parent start={{ current_pin_code: "999999" }} />)
    await click(suggestIn("State"))
    expect(screen.getByText(/could not find PIN code 999999/)).toBeTruthy()
    expect(held.form.current_state).toBe("")
  })

  it("says so when the PIN code has no area to suggest for the city", async () => {
    lookupAnswer = { locality: "", district: "Hyderabad", state: "Telangana" }
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await click(suggestIn("City"))
    expect(screen.getByText(/no area name to suggest/)).toBeTruthy()
  })
})

describe("Suggest buttons in the permanent address", () => {
  const permanentStart = { permanent_same_as_current: "false", permanent_pin_code: "500081" }

  it("are there too, one on State, District and City", () => {
    render(<Parent start={permanentStart} />)
    expect(suggestButtons()).toHaveLength(6)
  })

  it("read the permanent PIN code, not the current one", async () => {
    render(<Parent start={{ ...permanentStart, current_pin_code: "560001" }} />)
    await click(suggestIn("State", 1))
    expect(lookupSpy).toHaveBeenCalledWith("500081")
    expect(held.form.permanent_state).toBe("Telangana")
    expect(held.form.permanent_district).toBe("Hyderabad")
  })

  it("have exactly the fields of the present address: lines, State, District, PIN code, City, Landmark, Country", () => {
    render(<Parent start={permanentStart} />)
    const labelsIn = (heading: string) => {
      const start = screen.getByText(heading, { selector: ".sechead" })
      const labels: string[] = []
      for (let node = start.nextElementSibling; node && !node.classList.contains("sechead") && !node.classList.contains("togline"); node = node.nextElementSibling) {
        node.querySelectorAll("label").forEach(label => labels.push(label.textContent?.trim() ?? ""))
      }
      return labels
    }
    const wanted = ["Address line 1", "Address line 2", "State", "District", "PIN code", "City", "Landmark", "Country"]
    expect(labelsIn("CURRENT ADDRESS")).toEqual(wanted)
    expect(labelsIn("PERMANENT ADDRESS")).toEqual(wanted)
  })

  it("keep the permanent landmark and country apart from the present ones", async () => {
    render(<Parent start={permanentStart} />)
    const landmarks = screen.getAllByPlaceholderText("Near…")
    expect(landmarks).toHaveLength(2)
    fireEvent.change(landmarks[1], { target: { value: "Near the temple" } })
    expect((screen.getAllByPlaceholderText("Near…")[1] as HTMLInputElement).value).toBe("Near the temple")
    expect((screen.getAllByPlaceholderText("Near…")[0] as HTMLInputElement).value).toBe("")
  })

  it("fill the permanent city", async () => {
    render(<Parent start={permanentStart} />)
    await click(suggestIn("City", 1))
    expect(held.form.permanent_village).toBe("Cyberabad")
  })

  it("explain themselves when the permanent PIN code is empty", async () => {
    render(<Parent start={{ permanent_same_as_current: "false" }} />)
    await click(suggestIn("District", 1))
    expect(screen.getByText(/Enter the 6-digit PIN code first/)).toBeTruthy()
  })
})

describe("the PIN code drop-down", () => {
  it("lists the district's PIN codes once a state and district are chosen, and picking one fills the empty city with its area", async () => {
    render(<Parent start={{ current_state: "Telangana", current_district: "Hyderabad" }} />)
    expect(screen.getByText("2 PIN codes in Hyderabad")).toBeTruthy()
    const pinBox = screen.getByText("PIN code", { selector: "label" }).closest(".f") as HTMLElement
    await click(within(pinBox).getByRole("button", { name: /Select PIN code/ }))
    await click(screen.getByText("500081"))
    expect(held.form.current_pin_code).toBe("500081")
    expect(held.form.current_village).toBe("Cyberabad")
  })

  it("keeps a city the person already typed", async () => {
    render(<Parent start={{ current_state: "Telangana", current_district: "Hyderabad", current_village: "Kondapur" }} />)
    const pinBox = screen.getByText("PIN code", { selector: "label" }).closest(".f") as HTMLElement
    await click(within(pinBox).getByRole("button", { name: /Select PIN code/ }))
    await click(screen.getByText("500081"))
    expect(held.form.current_village).toBe("Kondapur")
  })

  it("is a plain 6-digit box until a state and district are chosen", () => {
    render(<Parent />)
    expect(screen.getAllByPlaceholderText("6-digit PIN code").length).toBeGreaterThan(0)
  })
})

describe("the PIN code fills the empty fields by itself", () => {
  it("fills state, district and city as soon as all 6 digits are in, and leaves a shorter number alone", async () => {
    render(<Parent />)
    const pinBox = () => screen.getAllByPlaceholderText("6-digit PIN code")[0]
    await act(async () => { fireEvent.change(pinBox(), { target: { value: "50008" } }) })
    expect(lookupSpy).not.toHaveBeenCalled()
    await act(async () => { fireEvent.change(pinBox(), { target: { value: "500081" } }) })
    expect(lookupSpy).toHaveBeenCalledWith("500081")
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Hyderabad")
    expect(held.form.current_village).toBe("Cyberabad")
  })

  it("never overwrites what the person already typed or chose", async () => {
    render(<Parent start={{ current_pin_code: "500081", current_village: "Kondapur", current_state: "Telangana" }} />)
    await act(async () => { await Promise.resolve() })
    expect(held.form.current_village).toBe("Kondapur")
    expect(held.form.current_state).toBe("Telangana")
    expect(held.form.current_district).toBe("Hyderabad")   // the one empty field is filled
  })

  it("does not fill a district that belongs to a different state from the one already chosen", async () => {
    render(<Parent start={{ current_pin_code: "500081", current_state: "Karnataka" }} />)
    await act(async () => { await Promise.resolve() })
    expect(held.form.current_state).toBe("Karnataka")
    expect(held.form.current_district).toBe("")
  })

  it("does nothing for a PIN code it does not know", async () => {
    lookupAnswer = null
    render(<Parent start={{ current_pin_code: "999999" }} />)
    await act(async () => { await Promise.resolve() })
    expect(held.form.current_state).toBe("")
  })
})

describe("a Suggest button lights up only when there is something to suggest", () => {
  it("shows Filled once its field holds what the PIN code says", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await act(async () => { await Promise.resolve() })
    expect(screen.getAllByRole("button", { name: /Filled/ })).toHaveLength(3)
    expect(screen.queryByRole("button", { name: /Suggest/ })).toBeNull()
  })

  it("goes back to Suggest when the person changes the field", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    await act(async () => { await Promise.resolve() })
    const cityBox = screen.getByText("City", { selector: "label" }).closest(".f") as HTMLElement
    fireEvent.change(within(cityBox).getByRole("textbox"), { target: { value: "Madhapur" } })
    expect(within(cityBox).getByRole("button", { name: /Suggest/ })).toBeTruthy()
  })

  it("is faded, not lit, while there is no PIN code", () => {
    render(<Parent />)
    for (const button of suggestButtons()) expect(button.className).toContain("is-waiting")
  })

  it("is not marked Filled for a PIN code it has not answered for yet", async () => {
    render(<Parent start={{ current_pin_code: "500081" }} />)
    expect(screen.queryByRole("button", { name: /Filled/ })).toBeNull()
    await act(async () => { await Promise.resolve() })
  })
})
