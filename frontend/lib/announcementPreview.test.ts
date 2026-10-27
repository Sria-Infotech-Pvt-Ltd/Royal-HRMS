import { describe, expect, it } from "vitest";
import { isLongBody, toggleExpanded } from "./announcementPreview";

describe("isLongBody", () => {
  it("short posts need no expand control", () => {
    expect(isLongBody("Office closed on Friday.")).toBe(false);
    expect(isLongBody("Line 1\nLine 2\nLine 3")).toBe(false);
    expect(isLongBody("   Short with spaces   \n")).toBe(false);
  });

  it("long or multi-paragraph posts are collapsible", () => {
    expect(isLongBody("x".repeat(221))).toBe(true);
    expect(isLongBody("Dear Team,\n\nDetails:\n- Date\n- Venue")).toBe(true);
    expect(isLongBody("a\r\nb\r\nc\r\nd")).toBe(true);
  });
});

describe("toggleExpanded", () => {
  it("cards expand and collapse independently", () => {
    const one = toggleExpanded(new Set(), 1);
    const both = toggleExpanded(one, 2);
    expect([...both].sort()).toEqual([1, 2]);           // expanding card 2 leaves card 1 expanded
    const back = toggleExpanded(both, 1);
    expect([...back]).toEqual([2]);                     // collapsing card 1 leaves card 2 alone
    expect([...one]).toEqual([1]);                      // previous state not mutated
  });
});
