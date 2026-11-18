// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

// The real wizard talks to a fake server that behaves like the backend: PATCH shallow-merges the sent fields into draft_data and
// answers with the whole draft; GET answers with what is stored.
const server = vi.hoisted(() => ({ draft: {} as Record<string, unknown>, patches: [] as Array<Record<string, unknown>> }));

vi.mock("@/lib/clientApi", () => {
  const action = () => ({
    id: "act-1", reason: "new_position", reason_display: "New position", effective_from: "2026-11-18", position: "p1",
    position_title: "Engineer", org_unit_name: "Eng", grade: "L2", employment_type: "Permanent", reserved_employee_id: "10000009",
    status: "draft", draft_data: JSON.parse(JSON.stringify(server.draft)), photo_url: null, created_employee: null,
  });
  return {
    default: {
      get: vi.fn(async (url: string) => {
        if (url.includes("hire-actions") && !url.includes("documents")) return { data: { data: action() } };
        if (url.includes("documents")) return { data: { data: [] } };
        if (url.includes("field-config")) return { data: { data: url.includes("education") ? { education: [], experience: [] } : {} } };
        return { data: { data: { results: [], states: [], districts: [], countries: [] } } };
      }),
      patch: vi.fn(async (_url: string, body: Record<string, unknown>) => {
        server.patches.push(body);
        server.draft = { ...server.draft, ...body };
        return { data: { data: action() } };
      }),
      post: vi.fn(async () => ({ data: { data: {} } })),
      delete: vi.fn(async () => ({ data: {} })),
    },
  };
});
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }), usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));

import HireWizardClient from "./HireWizardClient";
import { ToastProvider } from "@/components/ToastProvider";

afterEach(() => { cleanup(); server.draft = {}; server.patches = []; });

async function openFamilyStep() {
  render(<ToastProvider><HireWizardClient hireActionId="act-1" onClose={() => {}} onHired={() => {}} /></ToastProvider>);
  const tab = await screen.findByRole("button", { name: /Family/i });
  fireEvent.click(tab);
  return screen.findByRole("heading", { name: /Family members/i });
}

describe("Hire wizard: family details are saved", () => {
  it("saves a family member typed into the first card", async () => {
    await openFamilyStep();
    const card = await screen.findByRole("region", { name: /Family member: new/i });
    fireEvent.change(within(card).getByLabelText("Name"), { target: { value: "Asha Rao" } });
    await waitFor(() => {
      const saved = (server.draft.family_entries ?? []) as Array<{ name: string }>;
      expect(saved.some(entry => entry.name === "Asha Rao")).toBe(true);
    }, { timeout: 4000 });
  });

  it("saves a quick-added Father with his name and relationship", async () => {
    await openFamilyStep();
    fireEvent.click(screen.getByRole("button", { name: /Father/i }));
    const cards = await screen.findAllByRole("region", { name: /Family member: new/i });
    fireEvent.change(within(cards[cards.length - 1]).getByLabelText("Name"), { target: { value: "Ramesh Rao" } });
    await waitFor(() => {
      const saved = (server.draft.family_entries ?? []) as Array<{ name: string; relationship: string; gender: string }>;
      expect(saved.find(entry => entry.name === "Ramesh Rao")).toMatchObject({ relationship: "father", gender: "male" });
    }, { timeout: 4000 });
  });

  it("saves a nominee picked from the family list with its share", async () => {
    await openFamilyStep();
    fireEvent.click(screen.getByRole("button", { name: /Father/i }));
    const cards = await screen.findAllByRole("region", { name: /Family member: new/i });
    fireEvent.change(within(cards[cards.length - 1]).getByLabelText("Name"), { target: { value: "Ramesh Rao" } });
    const lane = screen.getByRole("region", { name: /EPF \+ EPS nomination/i });
    await waitFor(() => expect(within(lane).getByRole("button", { name: /Add nominee/i })).toHaveProperty("disabled", false));
    fireEvent.click(within(lane).getByRole("button", { name: /Add nominee/i }));
    const pick = await within(lane).findByLabelText("EPF + EPS nominee");
    const fatherId = ((server.draft.family_entries ?? []) as Array<{ id: string; name: string }>).find(entry => entry.name === "Ramesh Rao")?.id
      ?? Array.from((pick as HTMLSelectElement).options).find(option => /Ramesh/.test(option.text))?.value ?? "";
    fireEvent.change(pick, { target: { value: fatherId } });
    fireEvent.click(within(lane).getByRole("button", { name: /Fill the rest/i }));
    await waitFor(() => {
      const nominees = (server.draft.nominee_entries ?? []) as Array<{ family_member: string; share_percentage: string; scheme: string }>;
      expect(nominees).toHaveLength(1);
      expect(nominees[0]).toMatchObject({ scheme: "epf_eps", share_percentage: "100" });
      expect(nominees[0].family_member).toBe(fatherId);
    }, { timeout: 4000 });
  });

  it("keeps a resumed draft's family and saves an edit to it", async () => {
    server.draft = { family_entries: [{ id: "fam-1", name: "Meera Rao", relationship: "mother", date_of_birth: "", gender: "female", blood_group: "", is_dependent: true }] };
    await openFamilyStep();
    fireEvent.click(await screen.findByRole("button", { name: "Edit Meera Rao" }));
    const card = screen.getByRole("region", { name: /Family member: Meera Rao/i });
    fireEvent.change(within(card).getByLabelText("Name"), { target: { value: "Meera R Rao" } });
    await waitFor(() => {
      const saved = (server.draft.family_entries ?? []) as Array<{ id: string; name: string; is_dependent: boolean }>;
      expect(saved).toHaveLength(1);
      expect(saved[0]).toMatchObject({ id: "fam-1", name: "Meera R Rao", is_dependent: true });
    }, { timeout: 4000 });
  });

  it("saves the removal of a family member", async () => {
    server.draft = { family_entries: [
      { id: "fam-1", name: "Meera Rao", relationship: "mother", date_of_birth: "", gender: "female", blood_group: "", is_dependent: false },
      { id: "fam-2", name: "Ramesh Rao", relationship: "father", date_of_birth: "", gender: "male", blood_group: "", is_dependent: false },
    ] };
    await openFamilyStep();
    fireEvent.click(await screen.findByRole("button", { name: "Remove Meera Rao" }));
    await waitFor(() => {
      const saved = (server.draft.family_entries ?? []) as Array<{ id: string }>;
      expect(saved.map(entry => entry.id)).toEqual(["fam-2"]);
    }, { timeout: 4000 });
  });
});
