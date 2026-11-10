import { describe, expect, it } from "vitest";
import { chargeFor } from "./saasPricing";

describe("chargeFor (same as backend pricing.charge)", () => {
  it("Growth ₹99 × 20 employees, monthly, GST 18% added", () => {
    expect(chargeFor("99", "18", false, 20, "monthly")).toEqual({ months: 1, subtotal: 1980, gst: 356.4, total: 2336.4 });
  });

  it("yearly is 12 months", () => {
    expect(chargeFor("49.00", "18.00", false, 10, "yearly")).toEqual({ months: 12, subtotal: 5880, gst: 1058.4, total: 6938.4 });
  });

  it("an unset billing period counts as monthly", () => {
    expect(chargeFor("49", "18", false, 10, "").total).toBe(578.2);
  });

  it("GST included in the price", () => {
    expect(chargeFor("118", "18", true, 5, "monthly")).toEqual({ months: 1, subtotal: 590, gst: 90, total: 590 });
  });

  it("rounds GST half-up to the paisa like the server", () => {
    // 3 × 33.33 = 99.99; 18% = 17.9982 → 18.00
    expect(chargeFor("33.33", "18", false, 3, "monthly")).toEqual({ months: 1, subtotal: 99.99, gst: 18, total: 117.99 });
    // 1 × 10.05 at 5% = 0.5025 → 0.50
    expect(chargeFor("10.05", "5", false, 1, "monthly").gst).toBe(0.5);
  });

  it("large companies stay exact", () => {
    expect(chargeFor("149", "18", false, 100000, "yearly").total).toBe(210984000);
  });
});
