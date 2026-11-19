import { describe, expect, it } from "vitest";
import { describeStatsFailure } from "./statsFailure";

describe("describeStatsFailure", () => {
  it("explains each kind of failure in plain words", () => {
    expect(describeStatsFailure(401)).toMatch(/sign in again/);
    expect(describeStatsFailure(403)).toMatch(/permission/);
    expect(describeStatsFailure(500)).toMatch(/server had a problem/);
    expect(describeStatsFailure(null)).toMatch(/could not be reached/);
    expect(describeStatsFailure(404)).toMatch(/error 404/);
  });
});
