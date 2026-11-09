import { describe, expect, it } from "vitest";
import { feedbackProblem } from "./useInterviewFeedback";
import { directoryStatusLabel } from "@/app/dashboard/employees/_data";

describe("feedbackProblem", () => {
  const valid = { rating: 4, recommendation: "recommend", comments: "Strong problem solving." };

  it("accepts a rating, recommendation and real comments", () => {
    expect(feedbackProblem(valid)).toBe("");
  });

  it("requires a rating from 1 to 5", () => {
    expect(feedbackProblem({ ...valid, rating: 0 })).toMatch(/rating/i);
    expect(feedbackProblem({ ...valid, rating: 6 })).toMatch(/rating/i);
  });

  it("requires a recommendation", () => {
    expect(feedbackProblem({ ...valid, recommendation: "" })).toMatch(/recommend/i);
  });

  it("requires at least 10 characters of comments, ignoring surrounding spaces", () => {
    expect(feedbackProblem({ ...valid, comments: "   short   " })).toMatch(/at least 10/);
  });
});

describe("directoryStatusLabel", () => {
  it("shows Awaiting activation, not Onboarding, once the hire is complete but the account is not active", () => {
    expect(directoryStatusLabel({ status: "onboarding", lastWorkingDay: null, awaitingActivation: true })).toBe("Awaiting activation");
  });

  it("still shows Onboarding while the onboarding itself is incomplete", () => {
    expect(directoryStatusLabel({ status: "onboarding", lastWorkingDay: null, awaitingActivation: false })).toBe("Onboarding");
  });

  it("keeps account status separate from employment status: an active account is Active", () => {
    expect(directoryStatusLabel({ status: "active", lastWorkingDay: null })).toBe("Active");
  });
});
