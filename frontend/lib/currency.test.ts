import { describe, expect, it } from "vitest";
import { CURRENCIES, currencyLabel, formatMoney } from "./currency";

describe("formatMoney", () => {
  it("uses the currency symbol", () => {
    expect(formatMoney(49, "INR")).toBe("₹49");
    expect(formatMoney("49.00", "USD")).toBe("$49");
    expect(formatMoney(49, "EUR")).toBe("€49");
    expect(formatMoney(49, "GBP")).toBe("£49");
    expect(formatMoney(49, "CAD")).toBe("C$49");
  });

  it("groups INR the Indian way and others the international way", () => {
    expect(formatMoney(1234567.5, "INR")).toBe("₹12,34,567.5");
    expect(formatMoney(1234567.5, "USD")).toBe("$1,234,567.5");
  });

  it("keeps Arabic-script symbols readable next to the amount", () => {
    expect(formatMoney(49, "AED")).toBe("‎د.إ 49");
  });

  it("defaults to INR and falls back to the code for unknown currencies", () => {
    expect(formatMoney(49)).toBe("₹49");
    expect(formatMoney(49, "JPY")).toBe("JPY 49");
  });
});

describe("CURRENCIES", () => {
  it("lists the nine supported ISO codes with labels", () => {
    expect(CURRENCIES.map(c => c.code)).toEqual(["INR", "USD", "EUR", "GBP", "AED", "SAR", "CAD", "AUD", "SGD"]);
    expect(currencyLabel(CURRENCIES[0])).toBe("Indian Rupee (INR - ₹)");
  });
});
