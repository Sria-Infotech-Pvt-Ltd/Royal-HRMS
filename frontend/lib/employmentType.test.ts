import { describe, expect, it } from "vitest";
import { matchEmploymentType } from "./employmentType";

describe("matchEmploymentType", () => {
  it("keeps canonical values", () => expect(matchEmploymentType("Part-Time")).toBe("Part-Time"));
  it("matches case and spacing", () => {
    expect(matchEmploymentType("permanent")).toBe("Permanent");
    expect(matchEmploymentType("part time")).toBe("Part-Time");
  });
  it("maps common aliases", () => {
    expect(matchEmploymentType("Full Time")).toBe("Permanent");
    expect(matchEmploymentType("Contractor")).toBe("Contract");
  });
  it("returns blank for blank and unknown values unchanged", () => {
    expect(matchEmploymentType("")).toBe("");
    expect(matchEmploymentType("Apprentice")).toBe("Apprentice");
  });
});
