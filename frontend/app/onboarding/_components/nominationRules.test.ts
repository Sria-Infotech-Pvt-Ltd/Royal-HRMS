import { describe, expect, it } from "vitest";
import type { FamilyEntry, NomineeEntry } from "./familyNominationTypes";
import {
  ageInYears, duplicateRoleIds, equalShares, initialsOf, isMinor, namedMembers, presetFor, remainingFor, schemeState, schemeTotal, sharesIn,
} from "./nominationRules";

const TODAY = new Date(2026, 10, 17);                       // 17 Nov 2026
const person = (over: Partial<FamilyEntry> = {}): FamilyEntry => ({ id: "f1", name: "Asha", relationship: "child", date_of_birth: "", gender: "", blood_group: "", is_dependent: false, ...over });
const nominee = (over: Partial<NomineeEntry> = {}): NomineeEntry => ({ id: "n1", family_member: "f1", scheme: "epf_eps", share_percentage: "0", ...over });

describe("ageInYears / isMinor", () => {
  it("counts whole years and respects the birthday", () => {
    expect(ageInYears("2000-11-17", TODAY)).toBe(26);       // birthday today
    expect(ageInYears("2000-11-18", TODAY)).toBe(25);       // birthday tomorrow
    expect(ageInYears("2000-12-31", TODAY)).toBe(25);
    expect(ageInYears("2026-11-17", TODAY)).toBe(0);
  });
  it("gives no age for a missing, malformed or future date", () => {
    for (const bad of ["", "17-11-2000", "2000/11/17", "nonsense", "2027-01-01"]) expect(ageInYears(bad, TODAY), bad).toBeNull();
  });
  it("treats under 18 as a minor, exactly 18 as not, and an unknown age as not a minor", () => {
    expect(isMinor("2008-11-18", TODAY)).toBe(true);        // 17
    expect(isMinor("2008-11-17", TODAY)).toBe(false);       // 18 today
    expect(isMinor("", TODAY)).toBe(false);
  });
});

describe("initialsOf", () => {
  it.each([["Asha Rao", "AR"], ["meera", "M"], ["  anil   kumar  sharma ", "AK"], ["", "?"], ["   ", "?"]])("%j -> %j", (name, expected) => {
    expect(initialsOf(name)).toBe(expected);
  });
});

describe("scheme totals", () => {
  const list = [
    nominee({ id: "a", scheme: "epf_eps", share_percentage: "60" }), nominee({ id: "b", scheme: "epf_eps", share_percentage: "40" }),
    nominee({ id: "c", scheme: "gratuity", share_percentage: "30" }), nominee({ id: "d", scheme: "", share_percentage: "10" }),
    nominee({ id: "e", scheme: "both", share_percentage: "abc" }),
  ];
  it("adds the shares of each scheme separately, counting a blank scheme as EPF + EPS and a bad number as 0", () => {
    expect(schemeTotal(list, "epf_eps")).toBe(110);
    expect(schemeTotal(list, "gratuity")).toBe(30);
    expect(schemeTotal(list, "both")).toBe(0);
    expect(sharesIn(list, "epf_eps").map(entry => entry.id)).toEqual(["a", "b", "d"]);
  });
  it.each([[0, 0, "empty"], [0, 2, "short"], [60, 2, "short"], [100, 2, "complete"], [101, 2, "over"], [50, 0, "empty"]] as const)(
    "total %i with %i nominees is %s", (total, count, state) => expect(schemeState(total, count)).toBe(state),
  );
});

describe("equalShares", () => {
  it.each([[1, [100]], [2, [50, 50]], [3, [34, 33, 33]], [4, [25, 25, 25, 25]], [7, [15, 15, 14, 14, 14, 14, 14]], [0, []]] as const)(
    "%i nominee(s)", (count, expected) => expect(equalShares(count)).toEqual(expected),
  );
  it("always adds up to exactly 100", () => {
    for (let count = 1; count <= 25; count += 1) expect(equalShares(count).reduce((a, b) => a + b, 0)).toBe(100);
  });
});

describe("remainingFor", () => {
  const list = [nominee({ id: "a", share_percentage: "60" }), nominee({ id: "b", share_percentage: "30" }), nominee({ id: "c", scheme: "gratuity", share_percentage: "90" })];
  it("is what the other nominees of the same scheme leave unassigned, never below 0", () => {
    expect(remainingFor(list, "epf_eps", "b")).toBe(40);
    expect(remainingFor(list, "epf_eps", "a")).toBe(70);
    expect(remainingFor([nominee({ id: "x", share_percentage: "80" }), nominee({ id: "y", share_percentage: "80" })], "epf_eps", "z")).toBe(0);
  });
});

describe("family list hints", () => {
  it("presets father as male and mother as female, and nothing else", () => {
    expect(presetFor("father")).toEqual({ relationship: "father", gender: "male" });
    expect(presetFor("mother")).toEqual({ relationship: "mother", gender: "female" });
    expect(presetFor("child")).toEqual({ relationship: "child" });
    expect(presetFor("spouse")).toEqual({ relationship: "spouse" });
  });
  it("flags the second and later father or mother, but never children, siblings or a spouse", () => {
    const list = [person({ id: "1", relationship: "father" }), person({ id: "2", relationship: "father" }), person({ id: "3", relationship: "mother" }),
      person({ id: "4", relationship: "mother" }), person({ id: "5", relationship: "child" }), person({ id: "6", relationship: "child" }), person({ id: "7", relationship: "spouse" }), person({ id: "8", relationship: "spouse" })];
    expect([...duplicateRoleIds(list)].sort()).toEqual(["2", "4"]);
  });
  it("offers only people with a name as nominees", () => {
    expect(namedMembers([person({ id: "1", name: "Asha" }), person({ id: "2", name: "  " }), person({ id: "3", name: "" })]).map(entry => entry.id)).toEqual(["1"]);
  });
});
