// @vitest-environment jsdom
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

vi.mock("./BranchLocationPreview", () => ({ default: () => <div data-testid="map" /> }));
vi.mock("./LeaderFields", () => ({ default: () => <div data-testid="leader-fields" /> }));
vi.mock("@/components/ToggleSwitch", () => ({
  default: ({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) => (
    <label>{label}<input type="checkbox" checked={checked} onChange={event => onChange(event.target.checked)} /></label>
  ),
}));

import BranchFormBody, { type BranchAdminProps } from "./BranchFormBody";
import { EMPTY_BRANCH_FORM, EMPTY_LEADER, OTHER_CITY, type BranchForm } from "./_data";
import type { GstContext } from "./BranchLocationSection";
import { geofenceSummary } from "./branchFormCopy";

const STATES = [{ id: 1, name: "Telangana" }, { id: 2, name: "Karnataka" }];
const CITIES = [{ id: 10, name: "Mulugu" }, { id: 11, name: "Hyderabad" }];
const GST_TWO = [{ id: "1", gstin: "36AAA", state: "Telangana", place_of_business: "A" }, { id: "2", gstin: "36BBB", state: "Telangana", place_of_business: "B" }];
const NO_ADMIN: BranchAdminProps = { form: EMPTY_LEADER, setForm: () => {}, employees: [], seats: [], errors: {}, currentAdmin: null };
const cleared: string[][] = [];

interface HarnessProps { initial?: BranchForm; gstOptions?: typeof GST_TWO; errors?: Record<string, string>; admin?: Partial<BranchAdminProps> }

function Harness({ initial = EMPTY_BRANCH_FORM, gstOptions = [], errors = {}, admin = {} }: HarnessProps) {
  const [form, setForm] = useState(initial);
  const [newCity, setNewCity] = useState("");
  const gst: GstContext = {
    stateName: STATES.find(state => String(state.id) === form.state)?.name, options: gstOptions as unknown as GstContext["options"],
    missing: false, choiceRequired: gstOptions.length > 1,
  };
  return (
    <BranchFormBody
      form={form} onChange={patch => setForm(previous => ({ ...previous, ...patch }))} clearErrors={(...keys) => { cleared.push(keys); }} errors={errors}
      states={STATES} cities={form.state ? CITIES : []} citiesLoading={false} codeLoading={false} newCityName={newCity} setNewCityName={setNewCity} gst={gst}
      admin={{ ...NO_ADMIN, ...admin }}
    />
  );
}

beforeEach(() => { cleared.length = 0; });
afterEach(() => cleanup());

const optionalRow = (name: RegExp) => screen.getByRole("button", { name });

describe("one screen", () => {
  it("shows Where is it, Name and address and Office settings together, with no Next or Back", () => {
    render(<Harness />);
    for (const heading of ["Where is it?", "Name and address", "Office settings"]) expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.getByLabelText(/State\/Region/)).toBeTruthy();
    expect(screen.getByLabelText(/Company Code Name/)).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Active" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Next|Back/ })).toBeNull();
  });

  it("keeps the two optional parts folded, each saying what is set", () => {
    render(<Harness />);
    expect(optionalRow(/Company Code Admin/).getAttribute("aria-expanded")).toBe("false");
    expect(optionalRow(/Company Code Admin/).textContent).toContain("Not assigned");
    expect(optionalRow(/Attendance area/).getAttribute("aria-expanded")).toBe("false");
    expect(optionalRow(/Attendance area/).textContent).toContain("Off: people can punch in from anywhere");
    expect(screen.queryByTestId("leader-fields")).toBeNull();
    expect(screen.queryByLabelText("Enable Geofencing")).toBeNull();
  });

  it("opens and closes an optional part when its row is clicked", () => {
    render(<Harness />);
    fireEvent.click(optionalRow(/Company Code Admin/));
    expect(screen.getByTestId("leader-fields")).toBeTruthy();
    fireEvent.click(optionalRow(/Company Code Admin/));
    expect(screen.queryByTestId("leader-fields")).toBeNull();
  });
});

describe("optional parts open by themselves when they have something to show", () => {
  it("geofence is open from the start when it is already on, and its row summarises the radius", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, geofencing_enabled: true, allowed_radius_meters: "250" }} />);
    expect(optionalRow(/Attendance area/).getAttribute("aria-expanded")).toBe("true");
    expect(optionalRow(/Attendance area/).textContent).toContain("On: within 250 m of the office");
    expect(screen.getByLabelText(/Latitude/)).toBeTruthy();
  });

  it("a geofence error opens its row so the message cannot be hidden", () => {
    render(<Harness errors={{ latitude: "Latitude is required" }} />);   // geofence is off, so the row would start folded
    expect(optionalRow(/Attendance area/).getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(screen.getByLabelText("Enable Geofencing"));
    expect(screen.getByText("Latitude is required")).toBeTruthy();
  });

  it("an admin error opens the admin row; a current admin opens it and is named", () => {
    const { unmount } = render(<Harness admin={{ errors: { branchAdmin_email: "Enter a valid email" } }} />);
    expect(optionalRow(/Company Code Admin/).getAttribute("aria-expanded")).toBe("true");
    unmount();
    const currentAdmin = { employee: { id: "E1", uuid: "u1", employee_id: "E1", full_name: "Asha Rao", email: "a@x.com", branch: "Mulugu" }, positionId: "p1", positionTitle: "Branch Head" };
    render(<Harness admin={{ currentAdmin }} />);
    expect(optionalRow(/Company Code Admin/).textContent).toContain("Current admin: Asha Rao");
    expect(optionalRow(/Company Code Admin/).getAttribute("aria-expanded")).toBe("true");
  });

  it("someone chosen as the new admin is announced in the row", () => {
    render(<Harness admin={{ form: { ...EMPTY_LEADER, name: "New Person", email: "n@x.com" } }} />);
    expect(optionalRow(/Company Code Admin/).textContent).toContain("A new person will be invited when you save");
  });
});

describe("Where is it", () => {
  it("changing the state empties the city and the GST choice, and clears their messages", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, state: "1", city: "10", gst_registration: "7" }} />);
    fireEvent.change(screen.getByLabelText(/State\/Region/), { target: { value: "2" } });
    expect((screen.getByLabelText(/^City/) as HTMLSelectElement).value).toBe("");
    expect(cleared).toContainEqual(["state", "city", "new_city_name", "gst_registration"]);
  });

  it("'Other' city asks for a name and keeps only letters, spaces, apostrophes and hyphens", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, state: "1", city: OTHER_CITY }} />);
    const input = screen.getByLabelText("New city name") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Ware4ngal #1" } });
    expect(input.value).toBe("Warengal ");
  });

  it("asks for a GST registration only when the state has several", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, state: "1" }} gstOptions={GST_TWO} />);
    expect(screen.getByLabelText(/GST Registration/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/GST Registration/), { target: { value: "2" } });
    expect(cleared).toContainEqual(["gst_registration"]);
  });

  it("the summary line shows the code, the name and the place", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, state: "1", city: "10", branch_code: "MUL", branch_name: "Mulugu" }} />);
    expect(screen.getByLabelText("Company Code preview").textContent).toBe("MUL");
    expect(screen.getByRole("status", { name: "Company Code summary" }).textContent).toContain("Mulugu, Telangana");
  });
});

describe("Name and address, Office settings", () => {
  it("the company name keeps only the allowed characters, and the code box is read-only", () => {
    render(<Harness initial={{ ...EMPTY_BRANCH_FORM, branch_code: "MUL" }} />);
    const name = screen.getByLabelText(/Company Code Name/) as HTMLInputElement;
    fireEvent.change(name, { target: { value: "Mulugu @ HQ!" } });
    expect(name.value).toBe("Mulugu  HQ");
    expect((screen.getByLabelText("Company Code") as HTMLInputElement).readOnly).toBe(true);
  });

  it("the status switch, Headquarter and Metro change the form", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("radio", { name: "Inactive" }));
    expect(screen.getByRole("radio", { name: "Inactive" }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByLabelText(/Mark as Headquarter/));
    fireEvent.click(screen.getByLabelText(/Metro City/));
    expect((screen.getByLabelText(/Mark as Headquarter/) as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText(/Metro City/) as HTMLInputElement).checked).toBe(true);
  });
});

describe("Attendance area", () => {
  it("turning it on shows the fields and map, a preset sets the radius, and the row summary follows", () => {
    render(<Harness />);
    fireEvent.click(optionalRow(/Attendance area/));
    expect(screen.queryByLabelText(/Latitude/)).toBeNull();
    fireEvent.click(screen.getByLabelText("Enable Geofencing"));
    expect(screen.getByLabelText(/Latitude/)).toBeTruthy();
    expect(screen.getByTestId("map")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "250 m" }));
    expect((screen.getByLabelText(/Allowed Radius \(metres\)/) as HTMLInputElement).value).toBe("250");
    expect(optionalRow(/Attendance area/).textContent).toContain("On: within 250 m of the office");
    expect(cleared).toContainEqual(["latitude", "longitude", "allowed_radius_meters"]);
  });

  it("geofenceSummary words the folded row", () => {
    expect(geofenceSummary(false, "150")).toBe("Off: people can punch in from anywhere");
    expect(geofenceSummary(true, "150")).toBe("On: within 150 m of the office");
    expect(geofenceSummary(true, " ")).toBe("On: within ? m of the office");
  });
});
