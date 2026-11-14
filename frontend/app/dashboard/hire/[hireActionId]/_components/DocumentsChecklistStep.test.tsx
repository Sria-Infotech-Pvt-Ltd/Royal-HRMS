// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

// The REAL checklist; only the upload button (which needs the upload machinery) is a stub.
vi.mock("@/components/DocUploadButton", () => ({ default: ({ label }: { label: string }) => <button type="button">Upload {label}</button> }));

import DocumentsChecklistStep, { EMPTY_VERIFICATION, REQUIRED_DOC_KEYS } from "./DocumentsChecklistStep";

afterEach(() => cleanup());

function mount() {
  return render(
    <DocumentsChecklistStep
      documents={[]} uploading={null} error="" onUpload={vi.fn()} onDelete={vi.fn()}
      verification={EMPTY_VERIFICATION} onVerificationChange={vi.fn()} hasExperienceEntries
    />,
  );
}

/** The row (the bordered flex box) that holds a document's label. */
const rowOf = (label: string) => screen.getByText(label).closest("div.flex.items-center.justify-between") as HTMLElement;

const REQUIRED = ["PAN Card", "Aadhaar Card", "10th Certificate", "12th Certificate", "Degree Certificate"];
const OPTIONAL = ["Passport", "Experience Letter", "Cancelled Cheque", "Latest Payslips", "Signed Offer Letter", "Address Proof"];

describe("Hire wizard > Documents step labels", () => {
  it("never shows the word 'Required' as a pill any more", () => {
    mount();
    expect(screen.queryByText("Required")).toBeNull();
  });

  it.each(REQUIRED)("marks %s as required with a red asterisk", label => {
    mount();
    const mark = within(rowOf(label)).getByTitle("Required");
    expect(mark.textContent).toBe("*");
    expect(mark.className).toContain("req");               // the app's standard required mark (red, light and dark)
    expect(mark.getAttribute("aria-label")).toBe("required"); // read out as "required", not as a bare asterisk
    expect(within(rowOf(label)).queryByText("Optional")).toBeNull();
  });

  it.each(OPTIONAL)("marks %s as Optional, with no asterisk", label => {
    mount();
    expect(within(rowOf(label)).getByText("Optional")).toBeTruthy();
    expect(within(rowOf(label)).queryByTitle("Required")).toBeNull();
  });

  it("the Cancelled Cheque and the Signed Offer Letter are both Optional", () => {
    mount();
    for (const label of ["Cancelled Cheque", "Signed Offer Letter"]) {
      expect(within(rowOf(label)).getByText("Optional")).toBeTruthy();
    }
  });

  it("shows exactly five asterisks, one per required document", () => {
    mount();
    expect(screen.getAllByTitle("Required")).toHaveLength(REQUIRED.length);
  });
});

describe("Hire wizard > required documents that gate Next and the Review step", () => {
  it("are the five marked with an asterisk, so an optional document can never block a hire", () => {
    expect([...REQUIRED_DOC_KEYS].sort()).toEqual(
      ["aadhaar_card", "degree_certificate", "pan_card", "tenth_certificate", "twelfth_certificate"],
    );
    expect(REQUIRED_DOC_KEYS).not.toContain("cancelled_cheque");
    expect(REQUIRED_DOC_KEYS).not.toContain("signed_offer_letter");
  });
});
