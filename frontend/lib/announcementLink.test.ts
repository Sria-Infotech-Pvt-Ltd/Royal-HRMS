import { describe, expect, it } from "vitest"
import { announcementLinkHref, parseLinkedAnnouncementId } from "./announcementLink"

describe("announcementLinkHref", () => {
  it("opens the announcements page on that announcement", () => {
    expect(announcementLinkHref(42)).toBe("/dashboard/announcements?open=42")
    expect(announcementLinkHref("7")).toBe("/dashboard/announcements?open=7")
  })
  it("escapes anything that is not a plain id", () => {
    expect(announcementLinkHref("1&x=2")).toBe("/dashboard/announcements?open=1%26x%3D2")
  })
})

describe("parseLinkedAnnouncementId", () => {
  it("reads a plain positive whole number", () => {
    expect(parseLinkedAnnouncementId("42")).toBe(42)
    expect(parseLinkedAnnouncementId("0012")).toBe(12)
  })
  it("rejects a missing, empty or malformed value", () => {
    for (const value of [null, undefined, "", " ", "abc", "1.5", "-3", "4 2", "12abc", "0", "00", "1e3", "javascript:alert(1)"]) {
      expect(parseLinkedAnnouncementId(value)).toBeNull()
    }
  })
  it("rejects a number too large to be an id", () => {
    expect(parseLinkedAnnouncementId("99999999999999999999")).toBeNull()
  })
})
