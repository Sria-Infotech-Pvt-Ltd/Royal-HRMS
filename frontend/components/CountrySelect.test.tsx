// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest"
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react"
import CountrySelect from "./CountrySelect"

afterEach(cleanup)

const collator = new Intl.Collator("en", { sensitivity: "base" })

/** The labels the drop-down offers, in the order they are shown. */
async function optionsOf(mode: "name" | "demonym"): Promise<string[]> {
  render(<CountrySelect value="" onChange={() => {}} mode={mode} />)
  await act(async () => { fireEvent.click(screen.getByRole("button")) })
  const search = screen.getByPlaceholderText(mode === "demonym" ? "Search nationalities…" : "Search countries…")
  const list = search.parentElement?.querySelector("div[style*='overflow']") as HTMLElement
  return Array.from(list.children).map(node => node.textContent ?? "")
}

describe("CountrySelect lists A to Z", () => {
  it("lists countries A to Z, with India in its place among the I's", async () => {
    const names = await optionsOf("name")
    expect(names.length).toBeGreaterThan(190)
    expect(names.every((name, index) => index === 0 || collator.compare(names[index - 1], name) <= 0)).toBe(true)
    expect(names[0]).toBe("Afghanistan")
    expect(names.indexOf("India")).toBeGreaterThan(names.indexOf("Iceland"))
    expect(names.indexOf("India")).toBeLessThan(names.indexOf("Indonesia"))
  })

  it("lists nationalities A to Z by the nationality shown, not by the country behind it", async () => {
    const demonyms = await optionsOf("demonym")
    expect(demonyms.every((name, index) => index === 0 || collator.compare(demonyms[index - 1], name) <= 0)).toBe(true)
    expect(demonyms.indexOf("Emirati")).toBeLessThan(demonyms.indexOf("Ethiopian"))
    expect(demonyms.indexOf("Emirati")).toBeGreaterThan(demonyms.indexOf("Egyptian"))
  })

  it("shows each label once", async () => {
    const demonyms = await optionsOf("demonym")
    expect(new Set(demonyms).size).toBe(demonyms.length)
  })
})
