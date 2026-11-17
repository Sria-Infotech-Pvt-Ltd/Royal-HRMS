// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import AnnouncementsHeader from "./AnnouncementsHeader"
import AnnouncementStats from "./AnnouncementStats"
import AnnouncementToolbar from "./AnnouncementToolbar"
import AnnouncementEmptyState from "./AnnouncementEmptyState"
import AnnouncementSkeleton from "./AnnouncementSkeleton"

afterEach(cleanup)

describe("AnnouncementsHeader", () => {
  it("offers a Back button and calls it", () => {
    const onBack = vi.fn()
    render(<AnnouncementsHeader onBack={onBack} />)
    fireEvent.click(screen.getByRole("button", { name: /Back/ }))
    expect(onBack).toHaveBeenCalledTimes(1)
  })

  it("shows the title and has no Post Announcement button", () => {
    render(<AnnouncementsHeader onBack={vi.fn()} />)
    expect(screen.getByText("Announcements")).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Post Announcement/ })).toBeNull()
  })
})

describe("AnnouncementStats", () => {
  it("shows the four totals, each with a line of context", () => {
    render(<AnnouncementStats posts={4} pinned={1} reactions={10} views={60} />)
    expect(screen.getByText("Total Posts")).toBeTruthy()
    expect(screen.getByText("1 of 4 stay on top")).toBeTruthy()
    expect(screen.getByText("about 2.5 per post")).toBeTruthy()
    expect(screen.getByText("about 15 per post")).toBeTruthy()
  })

  it("says so plainly when nothing has been posted", () => {
    render(<AnnouncementStats posts={0} pinned={0} reactions={0} views={0} />)
    expect(screen.getByText("Nothing posted yet")).toBeTruthy()
    expect(screen.getByText("Nothing pinned")).toBeTruthy()
    expect(screen.getAllByText("No posts to average yet")).toHaveLength(2)
  })
})

describe("AnnouncementToolbar", () => {
  function setup(overrides: Partial<React.ComponentProps<typeof AnnouncementToolbar>> = {}) {
    const handlers = { onSearchText: vi.fn(), onCategory: vi.fn(), onSort: vi.fn(), onPinnedOnly: vi.fn(), onClear: vi.fn() }
    render(
      <AnnouncementToolbar
        searchText="" category="" sort="newest" pinnedOnly={false} hasFilters={false} shown={null} matching={null}
        {...handlers} {...overrides}
      />,
    )
    return handlers
  }

  it("reports what is typed, picked and switched", () => {
    const handlers = setup()
    fireEvent.change(screen.getByLabelText("Search announcements"), { target: { value: "diwali" } })
    expect(handlers.onSearchText).toHaveBeenCalledWith("diwali")
    fireEvent.click(screen.getByRole("button", { name: "Policy" }))
    expect(handlers.onCategory).toHaveBeenCalledWith("policy")
    fireEvent.click(screen.getByRole("button", { name: /Pinned only/ }))
    expect(handlers.onPinnedOnly).toHaveBeenCalledWith(true)
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "reactions" } })
    expect(handlers.onSort).toHaveBeenCalledWith("reactions")
  })

  it("offers every sort and marks the pinned switch when it is on", () => {
    setup({ pinnedOnly: true })
    expect(screen.getAllByRole("option").map(option => option.textContent)).toEqual(["Newest first", "Oldest first", "Most reactions", "Most views"])
    expect(screen.getByRole("button", { name: /Pinned only/ }).getAttribute("aria-pressed")).toBe("true")
  })

  it("shows a clear-search button only while there is text, and it empties the box", () => {
    const { onSearchText } = setup({ searchText: "abc" })
    fireEvent.click(screen.getByLabelText("Clear search"))
    expect(onSearchText).toHaveBeenCalledWith("")
  })

  it("summarises the list and offers Clear filters only when something is filtered", () => {
    const { onClear } = setup({ shown: 3, matching: 12, hasFilters: true })
    expect(screen.getByRole("status").textContent).toContain("Showing 3 of 12 posts")
    fireEvent.click(screen.getByRole("button", { name: /Clear filters/ }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })

  it("says when a filter matches nothing, and offers to clear it", () => {
    setup({ shown: 0, matching: 0, hasFilters: true })
    expect(screen.getByRole("status").textContent).toContain("No posts match")
    expect(screen.getByRole("button", { name: /Clear filters/ })).toBeTruthy()
  })

  it("stays silent on an empty feed with no filters, because the empty-state card already says so", () => {
    setup({ shown: 0, matching: 0 })
    expect(screen.queryByRole("status")).toBeNull()
  })

  it("has no Clear filters button on the plain list", () => {
    setup({ shown: 5, matching: 5 })
    expect(screen.getByRole("status").textContent).toContain("Showing 5 of 5 posts")
    expect(screen.queryByRole("button", { name: /Clear filters/ })).toBeNull()
  })

  it("shows no summary before the first load", () => {
    setup()
    expect(screen.queryByRole("status")).toBeNull()
  })
})

describe("AnnouncementEmptyState", () => {
  it("invites the poster to post when nothing exists yet", () => {
    const onCreate = vi.fn()
    render(<AnnouncementEmptyState hasFilters={false} canPost onCreate={onCreate} onClear={vi.fn()} />)
    expect(screen.getByText("No announcements yet")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /Post Announcement/ }))
    expect(onCreate).toHaveBeenCalledTimes(1)
  })

  it("tells a reader that posts will appear here, with no Post button", () => {
    render(<AnnouncementEmptyState hasFilters={false} canPost={false} onCreate={vi.fn()} onClear={vi.fn()} />)
    expect(screen.getByText(/will appear here/)).toBeTruthy()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("explains a filtered-empty list differently and offers to clear the filters", () => {
    const onClear = vi.fn()
    render(<AnnouncementEmptyState hasFilters canPost onCreate={vi.fn()} onClear={onClear} />)
    expect(screen.getByText("No announcements match")).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Post Announcement/ })).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /Clear filters/ }))
    expect(onClear).toHaveBeenCalledTimes(1)
  })
})

describe("AnnouncementSkeleton", () => {
  it("draws the requested number of placeholder cards and marks itself busy", () => {
    const { container } = render(<AnnouncementSkeleton count={2} />)
    expect(container.querySelectorAll(".ann-skel-card")).toHaveLength(2)
    expect(container.firstElementChild?.getAttribute("aria-busy")).toBe("true")
  })
})
