import { describe, expect, it } from "vitest";
import { tint } from "./colour";

describe("tint", () => {
  it("makes an rgba from a hex colour", () => {
    expect(tint("#16A34A", 0.16)).toBe("rgba(22,163,74,0.16)");
  });
  it("keeps a theme variable a variable, so it follows the theme", () => {
    expect(tint("var(--brand)", 0.06)).toBe("color-mix(in srgb, var(--brand) 6%, transparent)");
  });
});
