import { describe, expect, it } from "vitest"
import { averagePerPost, buildListParams, hasActiveFilters, type ListFilters } from "./_filters"

const PLAIN: ListFilters = { category: "", search: "", pinnedOnly: false, sort: "newest" }

describe("buildListParams", () => {
  it("sends only the page for an unfiltered list, exactly as the page always did", () => {
    expect(buildListParams(PLAIN, 1)).toEqual({ page: "1", page_size: "10" })
  })

  it("adds each option that is switched on", () => {
    expect(buildListParams({ category: "policy", search: "leave", pinnedOnly: true, sort: "views" }, 3, 20)).toEqual({
      page: "3", page_size: "20", category: "policy", search: "leave", pinned: "1", sort: "views",
    })
  })

  it("leaves out the default sort and an empty search", () => {
    const params = buildListParams({ ...PLAIN, category: "event" }, 2)
    expect(params).not.toHaveProperty("sort")
    expect(params).not.toHaveProperty("search")
    expect(params).not.toHaveProperty("pinned")
  })
})

describe("hasActiveFilters", () => {
  it("is false only when nothing narrows or reorders the list", () => {
    expect(hasActiveFilters(PLAIN)).toBe(false)
    expect(hasActiveFilters({ ...PLAIN, category: "policy" })).toBe(true)
    expect(hasActiveFilters({ ...PLAIN, search: "x" })).toBe(true)
    expect(hasActiveFilters({ ...PLAIN, pinnedOnly: true })).toBe(true)
    expect(hasActiveFilters({ ...PLAIN, sort: "oldest" })).toBe(true)
  })
})

describe("averagePerPost", () => {
  it("gives a short per-post figure, with one decimal below ten and none above", () => {
    expect(averagePerPost(7, 2)).toBe("about 3.5 per post")
    expect(averagePerPost(60, 4)).toBe("about 15 per post")
    expect(averagePerPost(0, 3)).toBe("about 0 per post")
  })

  it("is null when there are no posts to average over", () => {
    expect(averagePerPost(5, 0)).toBeNull()
  })
})
