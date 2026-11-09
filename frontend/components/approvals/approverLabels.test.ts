import { describe, expect, it } from "vitest";
import { l1Placeholder, optionLabel, personLine } from "./approverLabels";

describe("approver labels", () => {
  it("shows name, role, branch and department, leaving out what is blank", () => {
    expect(optionLabel({ full_name: "Asha Rao", role: "Delivery Manager", branch: "Kondapur", department: "Software Services" }))
      .toBe("Asha Rao — Delivery Manager · Kondapur · Software Services");
    expect(optionLabel({ full_name: "Asha Rao", role: "", branch: "", department: "" })).toBe("Asha Rao — No role set");
  });

  it("names a chosen person by name and role", () => {
    expect(personLine({ full_name: "Asha Rao", role: "HR Business Partner" })).toBe("Asha Rao — HR Business Partner");
  });

  it("says L1 follows the reporting manager only when the approval rule says so", () => {
    expect(l1Placeholder({ l1: "Reporting manager", l2: "HR partner", l1_kind: "reporting_manager", l2_kind: "hr" }))
      .toBe("Same as the reporting manager (approval rule)");
    expect(l1Placeholder({ l1: "HR partner", l2: "", l1_kind: "hr", l2_kind: "" })).toBe("Per the approval rule: HR partner");
    expect(l1Placeholder({ l1: "", l2: "", l1_kind: "", l2_kind: "" })).toBe("Per the approval rule");
  });
});
