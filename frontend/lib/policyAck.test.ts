import { describe, expect, it } from "vitest";
import { ackState, filterAckRows, initialDocFilter } from "./policyAck";

describe("ackState", () => {
  it("is not_required unless the document asks for acknowledgement", () => {
    expect(ackState({})).toBe("not_required");
    expect(ackState({ requires_acknowledgement: false, my_acknowledged_at: "2026-10-01T10:00:00Z" })).toBe("not_required");
  });

  it("is pending until the current version is acknowledged", () => {
    expect(ackState({ requires_acknowledgement: true, version: 2, my_acknowledged_at: null })).toBe("pending");
    expect(ackState({ requires_acknowledgement: true, version: 2, my_acknowledged_at: "2026-10-01T10:00:00Z" })).toBe("acknowledged");
  });
});

describe("filterAckRows", () => {
  const rows = [
    { employee_id: "E1", name: "A", branch: "X", department: "", acknowledged_at: "2026-10-01T10:00:00Z" },
    { employee_id: "E2", name: "B", branch: "X", department: "", acknowledged_at: null },
  ];
  it("filters by status", () => {
    expect(filterAckRows(rows, "all")).toHaveLength(2);
    expect(filterAckRows(rows, "pending").map(r => r.employee_id)).toEqual(["E2"]);
    expect(filterAckRows(rows, "acknowledged").map(r => r.employee_id)).toEqual(["E1"]);
  });
});

describe("initialDocFilter", () => {
  const map = { "All Documents": "", Policies: "policy", Forms: "form" } as const;
  it("opens the tab matching ?category=", () => {
    expect(initialDocFilter("policy", map, "All Documents")).toBe("Policies");
    expect(initialDocFilter(null, map, "All Documents")).toBe("All Documents");
    expect(initialDocFilter("unknown", map, "All Documents")).toBe("All Documents");
  });
});
