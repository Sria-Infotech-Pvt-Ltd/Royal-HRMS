import { describe, expect, it } from "vitest";
import { normaliseError } from "./clientApi";

describe("normaliseError", () => {
  it("uses the backend's message when the server actually replied", () => {
    const err = { response: { status: 400, data: { message: "Phone number is locked once onboarding is complete." } } };
    expect(normaliseError(err).message).toBe("Phone number is locked once onboarding is complete.");
  });

  it("falls back to a generic message when the server replied with no message", () => {
    const err = { response: { status: 500, data: {} } };
    expect(normaliseError(err).message).toBe("An unexpected error occurred.");
  });

  // A pure network failure (dropped connection, timeout, offline, CORS) never
  // gets a `response` at all — axios's own `.message` for that case is a raw
  // string like "Network Error", which must never be shown as if the server said it.
  it("shows a friendly message, not axios's raw 'Network Error', when the server was never reached", () => {
    const err = { message: "Network Error" };
    expect(normaliseError(err).message).toBe("Could not reach the server. Check your connection and try again.");
  });

  it("shows the same friendly message for a request timeout", () => {
    const err = { message: "timeout of 10000ms exceeded", code: "ECONNABORTED" };
    expect(normaliseError(err).message).toBe("Could not reach the server. Check your connection and try again.");
  });
});
