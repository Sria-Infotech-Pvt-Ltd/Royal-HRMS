import { readFileSync } from "node:fs"
import path from "node:path"
import { describe, expect, it } from "vitest"

const GLOBALS_CSS = readFileSync(path.resolve(__dirname, "../../globals.css"), "utf8")
const PAGES = ["_components/PerformanceOverviewClient.tsx", "_components/ManagerAppraisalWorkspace.tsx"]

describe("Performance pages: the header, the four KPI cards and the block under them are never glued together", () => {
  it("opts in to the plain-stack spacing, because its blocks sit in a plain wrapper that adds no gap", () => {
    for (const file of PAGES) {
      const source = readFileSync(path.resolve(__dirname, file), "utf8")
      expect(source, file).toContain('className="plain-stack"')
      expect(source, file).toContain('className="stats"')
    }
  })

  it("gives the header and the block under the cards the page's standard 18px", () => {
    expect(GLOBALS_CSS).toMatch(/\.plain-stack\s*>\s*\.pagehead\s*\+\s*\.stats\s*,\s*\.plain-stack\s*>\s*\.stats\s*\+\s*\*\s*\{[^}]*margin-top:\s*18px/)
  })

  it("is not applied globally, because pages built on the page's own flex column already have that gap and it would double", () => {
    expect(GLOBALS_CSS).not.toMatch(/(^|\n)\.pagehead\s*\+\s*\.stats/)
    expect(GLOBALS_CSS).not.toMatch(/(^|\n)\.stats\s*\+\s*\*/)
  })
})
