import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const GLOBALS_CSS = readFileSync(path.resolve(__dirname, "../../globals.css"), "utf8")
const PAGE_SOURCE = readFileSync(path.resolve(__dirname, "page.tsx"), "utf8")

describe("Settings page layout", () => {
  it("puts the four cards directly above the category band in a plain wrapper, which adds no gap by itself", () => {
    const cards = PAGE_SOURCE.indexOf('className="stats"')
    const band = PAGE_SOURCE.indexOf('className="settings-cats"')
    expect(cards).toBeGreaterThan(-1)
    expect(band).toBeGreaterThan(cards)
  })

  it("separates the category band from the cards above it with the page's 18px gap, so they never touch", () => {
    const rule = GLOBALS_CSS.match(/\.stats\s*\+\s*\.settings-cats\s*\{([^}]*)\}/)
    expect(rule).not.toBeNull()
    expect(rule?.[1]).toMatch(/margin-top:\s*18px/)
  })

  it("keeps the band's own space below it", () => {
    const band = GLOBALS_CSS.match(/\.settings-cats\s*\{([^}]*)\}/)
    expect(band?.[1]).toMatch(/margin-bottom:\s*20px/)
  })
})
