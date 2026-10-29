import { describe, expect, it } from "vitest";
import { EMPTY_CONTACT, contactFormError, groupByLevel, levelLabel, type CompanyContact } from "./contactMatrix";

const c = (id: number, level: number, order: number, name: string): CompanyContact => ({
  ...EMPTY_CONTACT, id, name, escalation_level: level, display_order: order, branch_name: "",
});

describe("groupByLevel", () => {
  it("groups by escalation level, first point of contact first, then by order and name", () => {
    const groups = groupByLevel([c(1, 2, 0, "Zed"), c(2, 1, 1, "Bee"), c(3, 1, 0, "Cee"), c(4, 1, 0, "Ann")]);
    expect(groups.map(g => g.level)).toEqual([1, 2]);
    expect(groups[0].contacts.map(x => x.name)).toEqual(["Ann", "Cee", "Bee"]);
  });

  it("labels levels", () => {
    expect(levelLabel(1)).toBe("First point of contact");
    expect(levelLabel(3)).toBe("Escalation level 3");
  });
});

describe("contactFormError", () => {
  it("needs a name and an email or phone", () => {
    expect(contactFormError({ ...EMPTY_CONTACT })).toMatch(/Name/);
    expect(contactFormError({ ...EMPTY_CONTACT, name: "HR Desk" })).toMatch(/email or a phone/);
    expect(contactFormError({ ...EMPTY_CONTACT, name: "HR Desk", phone: "0000000000" })).toBeNull();
    expect(contactFormError({ ...EMPTY_CONTACT, name: "HR Desk", email: "not-an-email" })).toMatch(/valid email/);
  });
});
