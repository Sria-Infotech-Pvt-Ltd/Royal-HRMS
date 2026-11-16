import { afterEach, describe, expect, it, vi } from "vitest"
import { searchAddress } from "./geocode"

function respondWith(body: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn(async () => ({ ok, json: async () => body })))
}

afterEach(() => vi.unstubAllGlobals())

describe("searchAddress", () => {
  it("converts coordinates to numbers and drops malformed or non-finite rows", async () => {
    respondWith([
      { display_name: "Road A, City", lat: "17.385044", lon: "78.486671" },
      { display_name: "Bad", lat: "north", lon: "78.4" },
      { display_name: "Missing lon", lat: "17.3" },
      "junk",
    ])
    expect(await searchAddress("Road A City")).toEqual([{ label: "Road A, City", latitude: 17.385044, longitude: 78.486671 }])
  })

  it("asks Nominatim for at most 5 results in jsonv2", async () => {
    respondWith([])
    await searchAddress("  Road A City  ")
    const url = String(vi.mocked(fetch).mock.calls[0][0])
    expect(url).toContain("https://nominatim.openstreetmap.org/search?")
    expect(url).toContain("format=jsonv2")
    expect(url).toContain("limit=5")
    expect(url).toContain("q=Road+A+City")
  })

  it("returns nothing when the response is not a list", async () => {
    respondWith({ error: "x" })
    expect(await searchAddress("Road A City")).toEqual([])
  })

  it("throws a friendly error on a non-OK response", async () => {
    respondWith([], false)
    await expect(searchAddress("Road A City")).rejects.toThrow(/unavailable/)
  })
})
