// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { API } from "@/lib/api/endpoints";
import ProfileCorrectionModal from "./ProfileCorrectionModal";
import type { ProfileChangeField } from "@/types/hrHelp";
import { CORRECTION_SECTIONS, OTHER_FIELD, OTHER_SECTION, fieldsForSection } from "./profileCorrectionFields";

const post = vi.fn();
vi.mock("@/lib/clientApi", () => ({ default: { post: (...args: unknown[]) => post(...args) } }));
const changeFields: ProfileChangeField[] = [
  { key: "full_name", section: "Personal details", label: "Full name", kind: "text", max_length: 150, choices: [], full_access_only: false, current_value: "Gadde Durga" },
];
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: changeFields, loading: false, error: null, refetch: vi.fn() }) }));

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

    fireEvent.change(selects()[1], { target: { value: "Marital status" } });   // HR cannot apply this one in a single step: no new value is asked
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(API.hrHelp.list, {
      topic: "profile_correction", priority: "normal",
      message: "Section: Personal details. Field to change: Marital status. Reason: Entered the wrong year",
    });
  });

  it("asks for the new value of a field HR can apply, and sends it with the request", async () => {
    const onSubmitted = vi.fn();
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={onSubmitted} />);
    fireEvent.change(selects()[1], { target: { value: "Full name" } });
    fireEvent.change(screen.getByPlaceholderText("Reason for correction"), { target: { value: "The name on my ID card differs" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    expect(await screen.findByText("Enter the new full name.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();

    fireEvent.change(screen.getByPlaceholderText("New full name"), { target: { value: "  Gadde Durga Prasad " } });
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalled());
    expect(post).toHaveBeenCalledWith(API.hrHelp.list, expect.objectContaining({
      message: "Section: Personal details. Field to change: Full name. Reason: The name on my ID card differs",
      change_new_value: "Gadde Durga Prasad",
    }));
  });

  it("shows the value on record now, read only, above the new value", () => {
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={vi.fn()} />);
    expect(screen.queryByLabelText(/Current full name/i)).toBeNull();
    fireEvent.change(selects()[1], { target: { value: "Full name" } });
    const current = screen.getByDisplayValue("Gadde Durga") as HTMLInputElement;
    expect(current.readOnly).toBe(true);
    expect(screen.getByText(/Current full name \(on record\)/)).toBeTruthy();
  });

  it("marks every required box with a star", () => {
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={vi.fn()} />);
    fireEvent.change(selects()[1], { target: { value: "Full name" } });
    for (const label of ["Section", "Field to change", "New full name", "Reason"]) {
      const element = screen.getByText((_, node) => node?.tagName === "LABEL" && node.textContent === `${label} *`);
      expect(element).toBeTruthy();
    }
  });
});

describe("ProfileCorrectionModal: bank details", () => {
  it("accepts only digits for an account number and capitals for an IFSC code, and explains the check", () => {
    // The mocked field list is replaced for these cases through the shared array the mock returns.
    changeFields.push(
      { key: "account_number", section: "Bank details", label: "Account number", kind: "account", max_length: 18, choices: [], full_access_only: false, is_sensitive: true, current_value: "••••••••3333" },
      { key: "ifsc_code", section: "Bank details", label: "IFSC code", kind: "ifsc", max_length: 11, choices: [], full_access_only: false, is_sensitive: true, current_value: "•••••••0001" },
    );
    render(<ProfileCorrectionModal onClose={vi.fn()} onSubmitted={vi.fn()} />);
    fireEvent.change(selects()[0], { target: { value: "Bank details" } });
    fireEvent.change(selects()[1], { target: { value: "Account number" } });
    expect(screen.getByDisplayValue("••••••••3333")).toBeTruthy();   // the number on record is masked
    const account = screen.getByPlaceholderText("9 to 18 digits") as HTMLInputElement;
    fireEvent.change(account, { target: { value: "12 34-ab5678" } });
    expect(account.value).toBe("12345678");
    expect(screen.getByText(/passbook or a cancelled cheque/)).toBeTruthy();

    fireEvent.change(selects()[1], { target: { value: "IFSC code" } });
    const ifsc = screen.getByPlaceholderText("e.g. SBIN0001234") as HTMLInputElement;
    fireEvent.change(ifsc, { target: { value: "sbin 0001234!" } });
    expect(ifsc.value).toBe("SBIN0001234");
  });
});
