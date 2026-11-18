import { describe, expect, it } from "vitest";
import { fieldsTheServerDidNotKeep } from "./savedDraftCheck";

describe("fieldsTheServerDidNotKeep", () => {
  const sent = { first_name: "Asha", last_name: "Rao", email: "a@x.com", branch: "Kondapur", pan_number: "ABCDE1234F", ifsc_code: "HDFC0001234" };

  it("is empty when the server holds everything that is on screen", () => {
    expect(fieldsTheServerDidNotKeep(sent, { ...sent })).toEqual([]);
  });

  it("names a field that is on screen but empty on the server", () => {
    expect(fieldsTheServerDidNotKeep(sent, { ...sent, branch: "" })).toEqual(["Company code"]);
  });

  it("names every missing field, and treats a missing key or a missing draft the same as empty", () => {
    expect(fieldsTheServerDidNotKeep(sent, { first_name: "Asha" })).toEqual(["Last name", "Personal email", "Company code", "PAN", "IFSC code"]);
    expect(fieldsTheServerDidNotKeep(sent, null)).toHaveLength(6);
  });

  it("ignores a field that is blank on screen too, and a server value that differs but is not empty", () => {
    expect(fieldsTheServerDidNotKeep({ ...sent, branch: "  " }, { ...sent, branch: "" })).toEqual([]);
    expect(fieldsTheServerDidNotKeep(sent, { ...sent, branch: "Mulugu" })).toEqual([]);
  });
});
