import { describe, expect, it } from "vitest";
import * as v from "./saasValidation";

describe("saasValidation", () => {
  it("names", () => {
    expect(v.businessName("Acme Pvt. Ltd (India)", "Company name")).toBeNull();
    expect(v.businessName("", "Company name")).toMatch(/required/);
    expect(v.businessName("12345")).not.toBeNull();
    expect(v.businessName("<script>")).not.toBeNull();
    expect(v.personName("R. K. D'Souza")).toBeNull();
    expect(v.personName("")).toBeNull();                       // optional
    expect(v.personName("John123")).not.toBeNull();
  });

  it("codes", () => {
    expect(v.planCode("growth-2")).toBeNull();
    for (const bad of ["4", "9plan", "My plan", "a", "UPPER"]) expect(v.planCode(bad)).not.toBeNull();
    expect(v.companyCode("acme1")).toBeNull();                 // upper-cased before checking
    for (const bad of ["", "AB", "1ABC", "NEW CO", "ADMIN"]) expect(v.companyCode(bad)).not.toBeNull();
  });

  it("email, phone, gstin", () => {
    expect(v.email("a@b.co")).toBeNull();
    for (const bad of ["", "a@", "@b.co", "no-at", "a b@c.com"]) expect(v.email(bad)).not.toBeNull();
    expect(v.email("", false)).toBeNull();
    expect(v.phone("+91 98765-43210")).toBeNull();
    for (const bad of ["call me", "12", "98765abc"]) expect(v.phone(bad)).not.toBeNull();
    expect(v.gstin("22AAAAA0000A1Z5")).toBeNull();
    expect(v.gstin("BADGSTIN")).not.toBeNull();
  });

  it("money and percentages", () => {
    expect(v.decimal("49.50")).toBeNull();
    for (const bad of ["abc", "-1", "1.999", "1e3", ""]) expect(v.decimal(bad)).not.toBeNull();
    expect(v.decimal("0", { minExclusive: true })).not.toBeNull();
    expect(v.decimal("100", { max: 100, what: "GST" })).toBeNull();
    expect(v.decimal("100.01", { max: 100, what: "GST" })).not.toBeNull();
    expect(v.decimal("", { isRequired: false })).toBeNull();
  });

  it("whole numbers with boundaries", () => {
    expect(v.wholeNumber("1")).toBeNull();
    expect(v.wholeNumber("100000")).toBeNull();
    for (const bad of ["0", "-5", "12.5", "ten", "100001"]) expect(v.wholeNumber(bad)).not.toBeNull();
    expect(v.wholeNumber("")).toBeNull();
    expect(v.wholeNumber("", { isRequired: true })).not.toBeNull();
  });

  it("dates", () => {
    expect(v.date("2026-11-03")).toBeNull();
    for (const bad of ["2026-02-30", "03-11-2026", "1999-12-31", ""]) expect(v.date(bad)).not.toBeNull();
    expect(v.date("", { isRequired: false })).toBeNull();
    expect(v.date("2999-01-01", { notFuture: true })).not.toBeNull();
  });

  it("references and API errors", () => {
    expect(v.reference("UTR-123/45 #A")).toBeNull();
    expect(v.reference("UTR<script>")).not.toBeNull();
    const err = { response: { data: { data: { name: ["Bad name."], new_company: { company_code: ["Taken."] } } } } };
    expect(v.apiFieldErrors(err)).toEqual({ name: "Bad name.", "new_company.company_code": "Taken." });
    expect(v.collect({ a: null, b: "x" })).toEqual({ b: "x" });
  });
});
