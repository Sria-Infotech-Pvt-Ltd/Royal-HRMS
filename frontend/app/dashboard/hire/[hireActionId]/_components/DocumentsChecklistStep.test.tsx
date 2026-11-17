// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";

// The REAL checklist; only the upload button (which needs the upload machinery) is a stub.
vi.mock("@/components/DocUploadButton", () => ({ default: ({ label }: { label: string }) => <button type="button">Upload {label}</button> }));

import DocumentsChecklistStep, { certificateTypeForLevel, EMPTY_VERIFICATION, REQUIRED_DOC_KEYS } from "./DocumentsChecklistStep";

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

  it.each(OPTIONAL)("marks %s with no asterisk and no label: nothing marked means nothing is demanded", label => {
    mount();
    expect(within(rowOf(label)).queryByText("Optional")).toBeNull();
    expect(within(rowOf(label)).queryByTitle("Required")).toBeNull();
  });

  it("the Cancelled Cheque and the Signed Offer Letter are both optional, so they carry no mark", () => {
    mount();
    for (const label of ["Cancelled Cheque", "Signed Offer Letter"]) {
      expect(within(rowOf(label)).queryByText("Optional")).toBeNull();
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

describe("Hire wizard > a certificate attached on the Education & experience step is not asked for again", () => {
  const entryDoc = (document_type: string, entry_ref: string, file_name: string) => ({
    id: `${document_type}-${entry_ref}`, document_type, document_type_display: document_type, entry_ref, file_name, file_size: 1000, uploaded_at: "2026-11-17",
  });
  const mountWith = (documents: ReturnType<typeof entryDoc>[]) => render(
    <DocumentsChecklistStep
      documents={documents} uploading={null} error="" onUpload={vi.fn()} onDelete={vi.fn()}
      verification={EMPTY_VERIFICATION} onVerificationChange={vi.fn()} hasExperienceEntries
    />,
  );

  it("files an SSC certificate as the 10th, an Intermediate one as the 12th, and anything else as the degree certificate", () => {
    expect(certificateTypeForLevel("ssc")).toBe("tenth_certificate");
    expect(certificateTypeForLevel("intermediate")).toBe("twelfth_certificate");
    for (const level of ["diploma", "bachelors", "masters", "doctorate", "other", ""]) expect(certificateTypeForLevel(level)).toBe("degree_certificate");
  });

  it("shows the 10th certificate as uploaded, with its file name, and offers no second upload", () => {
    mountWith([entryDoc("tenth_certificate", "e1", "ssc-memo.pdf")]);
    const row = rowOf("10th Certificate");
    expect(within(row).getByText("Uploaded")).toBeTruthy();
    expect(within(row).getByText(/ssc-memo\.pdf/)).toBeTruthy();
    expect(within(row).queryByRole("button")).toBeNull();
  });

  it("still asks for the certificates that were not attached there", () => {
    mountWith([entryDoc("tenth_certificate", "e1", "ssc-memo.pdf")]);
    expect(within(rowOf("12th Certificate")).getByRole("button", { name: /Upload 12th Certificate/ })).toBeTruthy();
    expect(within(rowOf("Degree Certificate")).getByRole("button", { name: /Upload Degree Certificate/ })).toBeTruthy();
  });

  it("counts several attached degrees as one satisfied row", () => {
    mountWith([entryDoc("degree_certificate", "e3", "btech.pdf"), entryDoc("degree_certificate", "e4", "mtech.pdf")]);
    const row = rowOf("Degree Certificate");
    expect(within(row).getByText("Uploaded")).toBeTruthy();
    expect(within(row).getByText(/2 files/)).toBeTruthy();
    expect(within(row).queryByRole("button")).toBeNull();
  });

  it("shows the experience letter as uploaded when one is attached to an employer", () => {
    mountWith([entryDoc("experience_letter", "x1", "relieving.pdf")]);
    expect(within(rowOf("Experience Letter")).getByText("Uploaded")).toBeTruthy();
  });

  it("is not satisfied by a standalone file in the wrong place: a PAN file attached to an entry does not count", () => {
    mountWith([entryDoc("pan_card", "e1", "pan.pdf")]);
    expect(within(rowOf("PAN Card")).getByRole("button", { name: /Upload PAN Card/ })).toBeTruthy();
  });
});
