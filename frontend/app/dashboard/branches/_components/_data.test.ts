import { describe, expect, it } from "vitest";
import { branchToForm, EMPTY_BRANCH_FORM, type Branch } from "./_data";

// Shaped like GET /branch/branches/<id>/ (BranchSerializer) returns it.
const SAVED: Branch = {
  id: 7, branch_code: "HYD-01", branch_name: "Hyderabad North", is_headquarter: true, is_metro: true,
  address: "Plot 1, Hitech City", state: 25, state_name: "Telangana", city: 314, city_name: "Hyderabad",
  gst_registration: "gst-uuid", gst_registration_gstin: "36ABCDE1234F1Z5", employees_count: 4,
  status: "inactive", geofencing_enabled: true, latitude: 17.462542, longitude: 78.369547,
  allowed_radius_meters: 300, has_coordinates: true,
};

describe("branchToForm", () => {
  it("fills every Edit field from the saved Company Code", () => {
    expect(branchToForm(SAVED)).toEqual({
      id: 7, branch_code: "HYD-01", branch_name: "Hyderabad North", address: "Plot 1, Hitech City",
      state: "25", city: "314", gst_registration: "gst-uuid", status: "inactive",
      is_headquarter: true, is_metro: true, geofencing_enabled: true,
      latitude: "17.462542", longitude: "78.369547", allowed_radius_meters: "300",
    });
  });

  it("uses the form defaults only where nothing is saved", () => {
    const form = branchToForm({
      ...SAVED, gst_registration: null, latitude: null, longitude: null, allowed_radius_meters: null,
      geofencing_enabled: false, status: "Active",
    });
    expect(form.gst_registration).toBe("");
    expect(form.latitude).toBe("");
    expect(form.longitude).toBe("");
    expect(form.allowed_radius_meters).toBe(EMPTY_BRANCH_FORM.allowed_radius_meters);
    expect(form.status).toBe("active");  // matches the Status <option> values
  });
});
