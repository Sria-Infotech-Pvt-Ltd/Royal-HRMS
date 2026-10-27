import { describe, expect, it } from "vitest";
import { NOT_ASSIGNED, assignedName } from "./assignedPerson";

describe("assignedName", () => {
  it("shows the assigned person's name", () => {
    expect(assignedName({ id: "DEM00012", name: "Anjali Sharma" })).toBe("Anjali Sharma");
    expect(assignedName({ id: "DEM00012", name: "  Priya Rao " })).toBe("Priya Rao");
  });

  it("shows Not assigned for null, missing or blank values — never the id", () => {
    expect(assignedName(null)).toBe(NOT_ASSIGNED);
    expect(assignedName(undefined)).toBe(NOT_ASSIGNED);
    expect(assignedName({ id: "DEM00012", name: null })).toBe(NOT_ASSIGNED);
    expect(assignedName({ id: "DEM00012", name: "   " })).toBe(NOT_ASSIGNED);
    expect(assignedName({ id: "DEM00012" })).toBe(NOT_ASSIGNED);
  });
});
