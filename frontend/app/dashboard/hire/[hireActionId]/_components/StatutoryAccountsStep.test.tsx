// @vitest-environment jsdom
import { useEffect, useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { IfscBankInfo } from "@/hooks/useIfscLookup";

// The REAL step, held by a real parent that keeps the state the way the Hire wizard and Edit Record do (`onChange={setStatutory}`).
// The IFSC lookup is a stub whose answer the test releases whenever it likes: the real one calls an outside service and can take
// seconds, which is exactly the window in which the old code lost the last IFSC character and every field typed meanwhile.
let waiting: { code: string; answer: (info: IfscBankInfo | null) => void }[];
vi.mock("@/hooks/useIfscLookup", () => ({
  useIfscLookup: () => ({ lookup: (code: string) => new Promise<IfscBankInfo | null>(resolve => { waiting.push({ code, answer: resolve }); }) }),
}));
vi.mock("@/components/DocUploadButton", () => ({ default: () => null }));
vi.mock("@/components/CountrySelect", () => ({ default: () => null }));
vi.mock("@/components/shared/DateInput", () => ({ default: () => null }));

import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "./StatutoryAccountsStep";

const HDFC: IfscBankInfo = { bank: "HDFC Bank", branch: "Kondapur", address: "Main Road", city: "Hyderabad", state: "Telangana" };
const IFSC = "HDFC0001234";

const heldBox: { current: StatutoryDraft } = { current: EMPTY_STATUTORY };   // what the parent holds, read by the tests
function Parent({ outside }: { outside?: Partial<StatutoryDraft> }) {
  const [value, setValue] = useState<StatutoryDraft>({ ...EMPTY_STATUTORY, ...outside });
  useEffect(() => { heldBox.current = value; });
  return (
    <>
      <StatutoryAccountsStep value={value} onChange={setValue} documents={[]} uploading={null} docError="" onUploadDoc={vi.fn()} onDeleteDoc={vi.fn()} />
      {/* What the Hire wizard does when "Scan & fill" picks a PAN: it updates the same state from outside the step. */}
      <button type="button" onClick={() => setValue(previous => ({ ...previous, pan_number: "ZZZZZ9999Z" }))}>scan-fills-pan</button>
    </>
  );
}

const box = (label: string) => {
  // The field whose <label> STARTS with this text ("PAN" must not match "Name as per Aadhaar" or the banner text).
  const labelElement = [...document.querySelectorAll("label")].find(element => (element.textContent ?? "").trim().startsWith(label));
  const field = labelElement?.closest(".f");
  if (!field) throw new Error(`no field labelled ${label}`);
  return field.querySelector("input") as HTMLInputElement;
};
const type = (input: HTMLInputElement, text: string) => fireEvent.change(input, { target: { value: text } });
const ifsc = () => screen.getByPlaceholderText("HDFC0001234") as HTMLInputElement;
const answerLookup = async (index: number, info: IfscBankInfo | null) => { await act(async () => { waiting[index].answer(info); }); };

beforeEach(() => { waiting = []; });
afterEach(() => cleanup());

describe("StatutoryAccountsStep: the IFSC lookup no longer undoes what was typed", () => {
  it("keeps all 11 characters of the IFSC after the bank is found (it used to drop the last one every time)", async () => {
    render(<Parent />);
    type(ifsc(), IFSC);
    await answerLookup(0, HDFC);
    expect(ifsc().value).toBe(IFSC);
    expect(heldBox.current.ifsc_code).toBe(IFSC);
  });

  it("fills the bank name AND the branch (the second fill no longer erases the first)", async () => {
    render(<Parent />);
    type(ifsc(), IFSC);
    await answerLookup(0, HDFC);
    expect(heldBox.current.bank_name).toBe("HDFC Bank");
    expect(heldBox.current.bank_branch_address).toBe("Kondapur, Main Road, Hyderabad, Telangana");
  });

  it("keeps everything typed while the lookup was still running (account holder, account number, PAN, Aadhaar)", async () => {
    render(<Parent />);
    type(ifsc(), IFSC);                                                    // the lookup starts and is slow ...
    type(box("PAN"), "abcde1234f");
    type(box("Aadhaar"), "123456789012");
    type(box("Account holder name"), "Asha Rao");
    type(box("Account number"), "0012345678");
    await answerLookup(0, HDFC);                                           // ... and answers only now
    expect(heldBox.current).toMatchObject({
      pan_number: "ABCDE1234F", aadhaar_number: "123456789012", account_holder_name: "Asha Rao", account_number: "0012345678",
      ifsc_code: IFSC, bank_name: "HDFC Bank",
    });
  });

  it("does not overwrite a bank name the person typed while the lookup was running, but still fills the empty branch", async () => {
    render(<Parent />);
    type(ifsc(), IFSC);
    type(box("Bank name"), "My own bank label");
    await answerLookup(0, HDFC);
    expect(heldBox.current.bank_name).toBe("My own bank label");
    expect(heldBox.current.bank_branch_address).toBe("Kondapur, Main Road, Hyderabad, Telangana");
  });

  it("does not overwrite a branch the person typed beforehand", async () => {
    render(<Parent outside={{ bank_branch_address: "Typed branch" }} />);
    type(ifsc(), IFSC);
    await answerLookup(0, HDFC);
    expect(heldBox.current.bank_branch_address).toBe("Typed branch");
    expect(heldBox.current.bank_name).toBe("HDFC Bank");
  });

  it("changes nothing when the code is not found (the IFSC and the rest stay as typed)", async () => {
    render(<Parent />);
    type(ifsc(), IFSC);
    type(box("Account number"), "555");
    await answerLookup(0, null);
    expect(heldBox.current).toMatchObject({ ifsc_code: IFSC, account_number: "555", bank_name: "", bank_branch_address: "" });
    expect(screen.getByText(/Couldn't auto-fill/)).toBeTruthy();
  });

  it("ignores the answer for an IFSC that was replaced meanwhile, and uses the answer for the new one", async () => {
    render(<Parent />);
    type(ifsc(), "HDFC0001234");
    type(ifsc(), "ICIC0005678");
    await answerLookup(0, HDFC);                                           // the old code's answer arrives late
    expect(heldBox.current.bank_name).toBe("");
    expect(heldBox.current.ifsc_code).toBe("ICIC0005678");
    await answerLookup(1, { bank: "ICICI Bank", branch: "Gachibowli", address: "", city: "Hyderabad", state: "Telangana" });
    expect(heldBox.current.bank_name).toBe("ICICI Bank");
    expect(heldBox.current.ifsc_code).toBe("ICIC0005678");
  });

  it("only looks the bank up for a complete, correctly shaped code, and upper-cases what is typed", () => {
    render(<Parent />);
    type(ifsc(), "hdfc000123");                                             // 10 characters: not complete
    expect(waiting).toHaveLength(0);
    expect(heldBox.current.ifsc_code).toBe("HDFC000123");
    type(ifsc(), "hdfc0001234");
    expect(waiting).toHaveLength(1);
    expect(heldBox.current.ifsc_code).toBe("HDFC0001234");
  });

  it("keeps a value another part of the wizard set from outside (Scan & fill) when the person then types here", async () => {
    render(<Parent />);
    fireEvent.click(screen.getByText("scan-fills-pan"));
    type(box("Account holder name"), "Asha Rao");
    expect(heldBox.current).toMatchObject({ pan_number: "ZZZZZ9999Z", account_holder_name: "Asha Rao" });
  });

  it("two changes made in the same moment add up instead of the second erasing the first", () => {
    render(<Parent />);
    act(() => {
      type(box("Account holder name"), "Asha Rao");
      type(box("Account number"), "123");
    });
    expect(heldBox.current).toMatchObject({ account_holder_name: "Asha Rao", account_number: "123" });
  });

  it("ordinary typing still works: PAN upper-case, Aadhaar and account number digits only", () => {
    render(<Parent />);
    type(box("PAN"), "abcde1234f");
    type(box("Aadhaar"), "12ab34");
    type(box("Account number"), "9x8y7");
    expect(heldBox.current).toMatchObject({ pan_number: "ABCDE1234F", aadhaar_number: "1234", account_number: "987" });
  });
});
