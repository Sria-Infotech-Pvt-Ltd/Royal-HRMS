import { describe, expect, it } from "vitest";
import { parseApiError } from "./apiError";

// What clientApi's normaliseError hands a catch block: { message, status, data, response: { data: { message, data } } }.
function normalised(message: string, data: unknown = {}, status = 400) {
  return { message, status, data, response: { data: { message, data } } };
}

describe("parseApiError", () => {
  it("puts a prefixed server message on its field, with a friendly label", () => {
    const parsed = parseApiError(normalised("gratuity_amount: Gratuity cannot be negative."), "Failed.");
    expect(parsed.fieldErrors).toEqual({ gratuity_amount: "Gratuity cannot be negative." });
    expect(parsed.message).toBe("Gratuity cannot be negative.");
  });

  it("replaces a raw key the person never typed with its label", () => {
    const parsed = parseApiError(normalised("phone: Must be 10 digits."), "Failed.");
    expect(parsed.message).toBe("Mobile number: Must be 10 digits.");
    expect(parsed.fieldErrors.phone).toBe("Must be 10 digits.");
  });

  it("keeps an upload message that has no field prefix as it is", () => {
    const message = "File size 8.0 MB exceeds the 5 MB limit.";
    const parsed = parseApiError(normalised(message, { file: [message] }), "Failed.");
    expect(parsed.message).toBe(message);
    expect(parsed.fieldErrors.file).toBe(message);
  });

  it("reads every field of the envelope's data", () => {
    const parsed = parseApiError(normalised("Fix the form.", { tds_amount: ["Too high."], start_date: ["Bad date."] }), "Failed.");
    expect(parsed.fieldErrors).toEqual({ tds_amount: "Too high.", start_date: "Bad date." });
  });

  it("understands a plain DRF detail and non_field_errors", () => {
    expect(parseApiError({ response: { status: 403, data: { detail: "Not allowed." } } }, "Failed.").message).toBe("Not allowed.");
    expect(parseApiError({ response: { data: { non_field_errors: ["Dates overlap."] } } }, "Failed.").message).toBe("Dates overlap.");
  });

  it("understands plain DRF field errors with no envelope", () => {
    const parsed = parseApiError({ response: { data: { end_date: ["Must be after start."] } } }, "Failed.");
    expect(parsed.fieldErrors).toEqual({ end_date: "Must be after start." });
    expect(parsed.message).toBe("End date: Must be after start.");
  });

  it("falls back when there is nothing to read", () => {
    expect(parseApiError(undefined, "Could not save.")).toEqual({ message: "Could not save.", fieldErrors: {}, status: null });
  });

  it("lets a form override a label", () => {
    const parsed = parseApiError(normalised("start_date: Not allowed."), "Failed.", { start_date: "From" });
    expect(parsed.message).toBe("From: Not allowed.");
  });
});
