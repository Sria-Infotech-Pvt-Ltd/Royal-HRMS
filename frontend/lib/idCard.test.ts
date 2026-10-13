import { describe, expect, it } from "vitest";
import { frontRows, idCardPrintCss, sampleCardData, termsFromText, type IdCardEmployee } from "./idCard";

const EMPTY: IdCardEmployee = {
  employee_id: null, full_name: null, designation: null, department: null, date_of_joining: null,
  date_of_birth: null, blood_group: null, location: null, photo_url: null,
  residential_address: null, phone: null, email: null,
};

describe("frontRows", () => {
  it("lists the front details in the reference order", () => {
    const rows = frontRows({
      ...EMPTY, employee_id: "EMP1", date_of_birth: "01/01/2000", date_of_joining: "02/02/2024",
      department: "IT", blood_group: "O+", location: "Hyderabad",
    });
    expect(rows.map(r => r.label)).toEqual(["Emp Code", "DOB", "DOJ", "Department", "Blood Group", "Location"]);
  });

  it("leaves missing values off the card instead of printing blanks", () => {
    const rows = frontRows({ ...EMPTY, employee_id: "EMP1", blood_group: "  " });
    expect(rows.map(r => r.key)).toEqual(["code"]);
  });
});

describe("termsFromText", () => {
  it("falls back to the defaults and fills in the company name", () => {
    expect(termsFromText("", "Property of {company}.\nNon-transferable.", "Acme"))
      .toEqual(["Property of Acme.", "Non-transferable."]);
  });

  it("uses custom lines and drops blank ones", () => {
    expect(termsFromText("One\n\n Two ", "Default", null)).toEqual(["One", "Two"]);
  });
});

describe("sampleCardData", () => {
  it("uses bracketed placeholders, never real-looking people, and respects hidden fields", () => {
    const company = { name: "Acme", logo_url: null, website: null, website_url: null, office_address: null };
    const data = sampleCardData(company, {
      terms: [], signature_url: null, signatory_label: "Authorised Signatory",
      show_date_of_birth: false, show_residential_address: true, show_contact_details: false,
    });
    expect(data.employee.full_name).toBe("[Employee Name]");
    expect(data.employee.date_of_birth).toBeNull();
    expect(data.employee.phone).toBeNull();
    expect(data.employee.residential_address).not.toBeNull();
  });
});

describe("idCardPrintCss", () => {
  it("prints each face on its own exact card-size page with no margins", () => {
    const css = idCardPrintCss("card");
    expect(css).toContain("@page { size: 50mm 85mm; margin: 0; }");
    expect(css).toContain("break-after: page");
  });

  it("prints both faces side by side on A4 with cut guides", () => {
    const css = idCardPrintCss("a4");
    expect(css).toContain("size: A4 portrait");
    expect(css).toContain("dashed");
    expect(css).not.toContain("break-after: page");
  });

  it("hides the rest of the app and keeps the card at a fixed size and colour", () => {
    for (const layout of ["card", "a4"] as const) {
      const css = idCardPrintCss(layout);
      expect(css).toContain("body > *:not(.idc-print-root) { display: none !important; }");
      expect(css).toContain(".idc-print-root { display: none; }");
      expect(css).toContain("width: 50mm; height: 85mm; overflow: hidden");
      expect(css).toContain("print-color-adjust: exact");
    }
  });
});
