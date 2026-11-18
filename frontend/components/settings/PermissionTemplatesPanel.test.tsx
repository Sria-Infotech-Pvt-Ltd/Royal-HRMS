// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import PermissionTemplatesPanel from "./PermissionTemplatesPanel"
import type { PermissionTemplate } from "./permissionTemplateTypes"

const item = (codename: string, is_sensitive = false) => ({ codename, action: codename.split(".")[1], description: "", is_sensitive })
const catalogue = { leave: [item("leave.view"), item("leave.approve")], payroll: [item("payroll.export", true)] }
const base: PermissionTemplate = {
  id: "1", name: "Manager", description: "Runs a team", can_manage_team: true, can_manage_branch: false, permission_codenames: ["leave.view", "payroll.export"],
  position_count: 2, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-10T00:00:00Z",
}
const templates: PermissionTemplate[] = [base, { ...base, id: "2", name: "Blank", description: "", can_manage_team: false, permission_codenames: [], position_count: 0 }]

const post = vi.fn()
const refetch = vi.fn()
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args), delete: vi.fn() } }))
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: templates, error: null, loading: false, refetch }) }))
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: vi.fn() }) }))
vi.mock("./PermissionTemplateEditor", () => ({ default: () => null }))
vi.mock("./ApplyTemplateModal", () => ({ default: () => null }))

beforeEach(() => { post.mockReset().mockResolvedValue({ data: {} }); refetch.mockReset() })
afterEach(() => cleanup())

describe("PermissionTemplatesPanel", () => {
  it("shows the summary numbers and a card per template with what it grants", () => {
    render(<PermissionTemplatesPanel catalogue={catalogue} canEdit />)
    expect(screen.getByText("Empty templates")).toBeTruthy()
    expect(screen.getByText("Applied to 2 positions")).toBeTruthy()
    expect(screen.getByText("1 sensitive")).toBeTruthy()
    expect(screen.getByText("Empty: grants nothing")).toBeTruthy()
  })

  it("filters and searches", () => {
    render(<PermissionTemplatesPanel catalogue={catalogue} canEdit />)
    fireEvent.click(screen.getByRole("button", { name: /^Empty/ }))
    expect(screen.queryByText("Runs a team")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /^All/ }))
    fireEvent.change(screen.getByLabelText("Search templates"), { target: { value: "zzz" } })
    expect(screen.getByText(/No template matches/)).toBeTruthy()
  })

  it("expands the details of a template", () => {
    render(<PermissionTemplatesPanel catalogue={catalogue} canEdit />)
    fireEvent.click(screen.getByRole("button", { name: "Show details" }))
    expect(screen.getByRole("button", { name: "Hide details" })).toBeTruthy()
  })

  it("duplicates a template under a new name with the same access", async () => {
    render(<PermissionTemplatesPanel catalogue={catalogue} canEdit />)
    fireEvent.click(screen.getAllByRole("button", { name: /Duplicate/ })[0])
    await waitFor(() => expect(post).toHaveBeenCalled())
    expect(post.mock.calls[0][1]).toMatchObject({ name: "Blank (copy)", codenames: [] })
  })

  it("hides edit actions without permission", () => {
    render(<PermissionTemplatesPanel catalogue={catalogue} canEdit={false} />)
    expect(screen.queryByRole("button", { name: /Duplicate/ })).toBeNull()
    expect(screen.queryByRole("button", { name: /New template/ })).toBeNull()
  })
})
