// @vitest-environment jsdom
import { useEffect, useRef, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

vi.mock("@/components/shared/DateInput", () => ({
  default: ({ value, onChange }: { value: string; onChange: (iso: string) => void }) => (
    <input aria-label="Date of birth" value={value} onChange={event => onChange(event.target.value)} />
  ),
}));

import FamilyNominationStep, { type FamilyEntry, type NomineeEntry } from "./FamilyNominationStep";

const member = (over: Partial<FamilyEntry> = {}): FamilyEntry => ({ id: "f1", name: "Asha Rao", relationship: "spouse", date_of_birth: "", gender: "", blood_group: "", is_dependent: false, ...over });
const nominee = (over: Partial<NomineeEntry> = {}): NomineeEntry => ({ id: "n1", family_member: "f1", scheme: "epf_eps", share_percentage: "0", ...over });

// A real parent that behaves like the Hire wizard: functional state updates, a fresh temp id for each added entry, and add buttons
// that take no arguments.
const stateBox: { current: { family: FamilyEntry[]; nominees: NomineeEntry[] } } = { current: { family: [], nominees: [] } };   // what the parent holds, read by the tests
function Parent({ family = [], nominees = [], error = null }: { family?: FamilyEntry[]; nominees?: NomineeEntry[]; error?: string | null }) {
  const [familyList, setFamily] = useState(family);
  const [nomineeList, setNominees] = useState(nominees);
  const counter = useRef(0);
  useEffect(() => { stateBox.current = { family: familyList, nominees: nomineeList }; });
  return (
    <FamilyNominationStep
      familyEntries={familyList} nomineeEntries={nomineeList} error={error}
      onAddFamily={() => { const id = `temp-f${++counter.current}`; setFamily(p => [...p, { id, name: "", relationship: "child", date_of_birth: "", gender: "", blood_group: "", is_dependent: false }]); }}
      onFamilyFieldChange={(id, field, value) => setFamily(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
      onRemoveFamily={id => setFamily(p => p.filter(e => e.id !== id))}
      onAddNominee={() => { const id = `temp-n${++counter.current}`; setNominees(p => [...p, { id, family_member: "", scheme: "epf_eps", share_percentage: "0" }]); }}
      onNomineeFieldChange={(id, field, value) => setNominees(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
      onRemoveNominee={id => setNominees(p => p.filter(e => e.id !== id))}
    />
  );
}

const click = (name: string | RegExp) => fireEvent.click(screen.getByRole("button", { name }));
const lane = (label: string) => screen.getByRole("region", { name: `${label} nomination` });
const bar = (label: string) => screen.getByRole("progressbar", { name: `${label} shares assigned` });

beforeEach(() => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date(2026, 10, 17)); });
afterEach(() => { vi.useRealTimers(); cleanup(); });

describe("Family & nomination: family members", () => {
  it("starts with a friendly empty state, quick-add buttons, and no way to add a nominee yet", () => {
    render(<Parent />);
    expect(screen.getByText(/No family members yet/)).toBeTruthy();
    for (const name of ["Father", "Mother", "Spouse", "Child", "Someone else"]) expect(screen.getByRole("button", { name: new RegExp(name) })).toBeTruthy();
    expect(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }).getAttribute("aria-disabled")).toBe("true");
    expect(screen.getAllByText("No nominee yet")).toHaveLength(3);
  });

  it("pressing Add nominee with nobody to nominate explains why and adds a family card to type into, instead of doing nothing", () => {
    render(<Parent />);
    expect(screen.queryByRole("alert")).toBeNull();
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }));
    expect(screen.getByRole("alert").textContent).toMatch(/nobody in it yet/);
    expect(screen.getByLabelText(/Family member/)).toBeTruthy();                       // the new, empty card
    expect(screen.getAllByText("No nominee yet")).toHaveLength(3);                     // and no nominee was created
  });

  it("the explanation goes away once a family member has a name", () => {
    render(<Parent />);
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Asha Rao" } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }).getAttribute("aria-disabled")).toBe("false");
  });

  it("quick-add Father adds an open card with Father and Male already chosen (the callers' add buttons take no arguments)", () => {
    render(<Parent />);
    click(/Father/);
    const card = screen.getByRole("region", { name: "Family member: new" });
    expect((within(card).getByLabelText("Relationship") as HTMLSelectElement).value).toBe("father");
    expect((within(card).getByLabelText("Gender") as HTMLSelectElement).value).toBe("male");
    expect(stateBox.current.family).toHaveLength(1);
  });

  it("quick-add Mother presets Female; Spouse and Child preset only the relationship; Someone else keeps the default", () => {
    render(<Parent />);
    click(/Mother/); click(/Spouse/); click(/Child/); click("Someone else");
    expect(stateBox.current.family.map(entry => [entry.relationship, entry.gender])).toEqual([["mother", "female"], ["spouse", ""], ["child", ""], ["child", ""]]);
  });

  it("a new card stays open while the name is typed, then 'Done' closes it and 'Edit' opens it again", () => {
    render(<Parent />);
    click(/Spouse/);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Asha Rao" } });
    expect(screen.getByLabelText("Name")).toBeTruthy();                      // it did not collapse on the first keystroke
    click("Close Asha Rao");
    expect(screen.queryByLabelText("Name")).toBeNull();
    expect(screen.getByRole("region", { name: "Family member: Asha Rao" })).toBeTruthy();
    click("Edit Asha Rao");
    expect(screen.getByLabelText("Name")).toBeTruthy();
  });

  it("a person already saved with a name starts closed, showing relationship, age and Dependent", () => {
    render(<Parent family={[member({ name: "Meera", relationship: "child", date_of_birth: "2015-05-01", is_dependent: true })]} />);
    const card = screen.getByRole("region", { name: "Family member: Meera" });
    expect(within(card).getByText("Child")).toBeTruthy();
    expect(within(card).getByText("11 yrs")).toBeTruthy();
    expect(within(card).getByText("Dependent")).toBeTruthy();
    expect(within(card).queryByLabelText("Name")).toBeNull();
  });

  it("the summary counts only people who have a name, and dependants", () => {
    render(<Parent family={[member({ id: "a", name: "Asha", is_dependent: true }), member({ id: "b", name: "Vikram" }), member({ id: "c", name: "" })]} />);
    const summary = screen.getByRole("status", { name: "Summary" });
    expect(summary.textContent).toContain("2 family members");
    expect(summary.textContent).toContain("1 dependant");
  });

  it("warns on a second father or mother, but not on children", () => {
    render(<Parent family={[member({ id: "1", name: "A", relationship: "father" }), member({ id: "2", name: "B", relationship: "father" }), member({ id: "3", name: "C", relationship: "child" }), member({ id: "4", name: "D", relationship: "child" })]} />);
    expect(screen.getAllByRole("note")).toHaveLength(1);
    expect(within(screen.getByRole("region", { name: "Family member: B" })).getByRole("note").textContent).toBe("Another father is already listed.");
  });

  it("removes a person", () => {
    render(<Parent family={[member({ id: "a", name: "Asha" }), member({ id: "b", name: "Vikram" })]} />);
    click("Remove Asha");
    expect(stateBox.current.family.map(entry => entry.name)).toEqual(["Vikram"]);
  });

  it("shows an error from the page above", () => {
    render(<Parent error="Could not save the family list." />);
    expect(screen.getByText("Could not save the family list.")).toBeTruthy();
  });
});

describe("Family & nomination: nominations", () => {
  const family = [member({ id: "f1", name: "Asha Rao" }), member({ id: "f2", name: "Vikram Rao", relationship: "father" })];
  const pick = (laneLabel: string, nth: number, memberId: string) => fireEvent.change(within(lane(laneLabel)).getAllByLabelText(`${laneLabel} nominee`)[nth], { target: { value: memberId } });
  const share = (laneLabel: string, nth: number, value: string) => fireEvent.change(within(lane(laneLabel)).getAllByLabelText(label => label.startsWith(`${laneLabel} share for`))[nth], { target: { value } });

  it("'Add nominee' in a lane puts the new nominee in THAT scheme, and a nominee can be added once someone has a name", () => {
    render(<Parent family={family} />);
    fireEvent.click(within(lane("Gratuity")).getByRole("button", { name: /Add nominee/ }));
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }));
    expect(stateBox.current.nominees.map(entry => entry.scheme).sort()).toEqual(["epf_eps", "gratuity"]);
    expect(within(lane("Gratuity")).getAllByLabelText("Gratuity nominee")).toHaveLength(1);
  });

  it("the bar and the message follow the shares: short, complete, over", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "f1", share_percentage: "60" })]} />);
    expect(bar("EPF + EPS").getAttribute("aria-valuenow")).toBe("60");
    expect(within(lane("EPF + EPS")).getByRole("status").textContent).toBe("40% still to assign");
    share("EPF + EPS", 0, "100");
    expect(within(lane("EPF + EPS")).getByRole("status").textContent).toBe("Complete: 100%");
    share("EPF + EPS", 0, "120");
    expect(within(lane("EPF + EPS")).getByRole("status").textContent).toBe("Over by 20%: lower a share");
    expect(bar("EPF + EPS").getAttribute("aria-valuenow")).toBe("100");               // the bar itself never overflows
  });

  it("'Fill the rest' gives a nominee whatever the others in the scheme leave", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "f1", share_percentage: "60" }), nominee({ id: "b", family_member: "f2", share_percentage: "0" })]} />);
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: "Fill the rest (40%)" }));
    expect(stateBox.current.nominees.find(entry => entry.id === "b")?.share_percentage).toBe("40");
    expect(within(lane("EPF + EPS")).getByRole("status").textContent).toBe("Complete: 100%");
  });

  it("'Split equally' needs two nominees and divides 100 between them, three ways as 34 / 33 / 33", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "f1" })]} />);
    expect(within(lane("EPF + EPS")).queryByRole("button", { name: "Split equally" })).toBeNull();
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }));
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: /Add nominee/ }));
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: "Split equally" }));
    expect(stateBox.current.nominees.map(entry => entry.share_percentage)).toEqual(["34", "33", "33"]);
  });

  it("the same person cannot be picked twice in one scheme, but can be in another", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "f1" }), nominee({ id: "b", family_member: "" })]} />);
    const second = within(lane("EPF + EPS")).getAllByLabelText("EPF + EPS nominee")[1];
    const optionFor = (name: string) => within(second).getByRole("option", { name: new RegExp(name) }) as HTMLOptionElement;
    expect(optionFor("Asha Rao").disabled).toBe(true);
    expect(optionFor("Vikram Rao").disabled).toBe(false);
    fireEvent.click(within(lane("Gratuity")).getByRole("button", { name: /Add nominee/ }));
    expect((within(within(lane("Gratuity")).getByLabelText("Gratuity nominee")).getByRole("option", { name: /Asha Rao/ }) as HTMLOptionElement).disabled).toBe(false);
  });

  it("only offers people who have a name (plus anyone already chosen)", () => {
    render(<Parent family={[member({ id: "f1", name: "Asha" }), member({ id: "f2", name: "" })]} nominees={[nominee({ id: "a", family_member: "" })]} />);
    const options = within(within(lane("EPF + EPS")).getByLabelText("EPF + EPS nominee")).getAllByRole("option").map(option => option.textContent);
    expect(options).toEqual(["— Select from family —", "Asha (Spouse)"]);
  });

  it("tells you when a nominee is under 18", () => {
    render(<Parent family={[member({ id: "f1", name: "Meera", relationship: "child", date_of_birth: "2015-05-01" })]} nominees={[nominee({ id: "a", family_member: "f1", share_percentage: "100" })]} />);
    expect(within(lane("EPF + EPS")).getByRole("note").textContent).toContain("Meera is under 18");
  });

  it("marks a nominated person's card with 'Nominee' and shows each scheme's total in the summary", () => {
    render(<Parent family={[member({ id: "f1", name: "Asha" }), member({ id: "f2", name: "Vikram" })]} nominees={[nominee({ id: "a", family_member: "f1", share_percentage: "100" }), nominee({ id: "b", family_member: "f1", scheme: "gratuity", share_percentage: "50" })]} />);
    expect(within(screen.getByRole("region", { name: "Family member: Asha" })).getByText("Nominee")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Family member: Vikram" })).queryByText("Nominee")).toBeNull();
    const summary = screen.getByRole("status", { name: "Summary" });
    expect(summary.textContent).toContain("EPF + EPS 100%");
    expect(summary.textContent).toContain("Gratuity 50%");
  });

  it("choosing a person and a share flows back to the parent exactly as before", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "" })]} />);
    pick("EPF + EPS", 0, "f2");
    share("EPF + EPS", 0, "70");
    expect(stateBox.current.nominees[0]).toMatchObject({ family_member: "f2", scheme: "epf_eps", share_percentage: "70" });
  });

  it("removes a nominee", () => {
    render(<Parent family={family} nominees={[nominee({ id: "a", family_member: "f1" }), nominee({ id: "b", family_member: "f2" })]} />);
    fireEvent.click(within(lane("EPF + EPS")).getByRole("button", { name: "Remove EPF + EPS nominee Asha Rao" }));
    expect(stateBox.current.nominees.map(entry => entry.id)).toEqual(["b"]);
  });
});
