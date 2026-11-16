// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import ProfileCorrectionModal from "./ProfileCorrectionModal";
import { CORRECTION_SECTIONS, OTHER_FIELD, OTHER_SECTION, fieldsForSection } from "./profileCorrectionFields";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));

beforeEach(() => post.mockReset().mockResolvedValue({ data: {} }));
afterEach(() => cleanup());

function selects(): [HTMLSelectElement, HTMLSelectElement] {
  const [section, field] = screen.getAllByRole("combobox") as HTMLSelectElement[];
  return [section, field];
}

describe("profileCorrectionFields", () => {
  it("lists fields per section, and only the free-text field for Other", () => {
    expect(fieldsForSection("Bank details")).toContain("IFSC code");
    expect(fieldsForSection(OTHER_SECTION)).toEqual([OTHER_FIELD]);
    expect(fieldsForSection("Nope")).toEqual([]);
    expect(CORRECTION_SECTIONS.map(entry => entry.value)).toEqual([
      "Personal details", "Contact & address", "Emergency contact", "Bank details", "Family & nomination", "Other",
    ]);
  });
});

describe("ProfileCorrectionModal", () => {
  it("offers the fields of the chosen section and clears the field when the section changes", () => {
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={vi.fn()} />);
    const [section, field] = selects();
    expect(field.value).toBe("");
    fireEvent.change(field, { target: { value: "Date of birth" } });
    expect(field.value).toBe("Date of birth");
    fireEvent.change(section, { target: { value: "Bank details" } });
    expect(selects()[1].value).toBe("");
    expect(Array.from(selects()[1].options).map(option => option.value)).toEqual(["", ...fieldsForSection("Bank details")]);
  });

  it("refuses to submit without a field, then posts the unchanged message format", async () => {
    const onSubmitted = vi.fn();
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={onSubmitted} />);
    fireEvent.change(screen.getByPlaceholderText("Reason for correction"), { target: { value: "  Entered the wrong year  " } });
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByText("Please choose which field needs to change.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(selects()[1], { target: { value: "Date of joining" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(API.hrHelp.list, {
      topic: "profile_correction", priority: "normal",
      message: "Section: Personal details. Field to change: Date of joining. Reason: Entered the wrong year",
    });
  });
});
