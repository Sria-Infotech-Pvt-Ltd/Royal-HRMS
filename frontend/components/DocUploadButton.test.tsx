// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import DocUploadButton, { type HireDocument } from "./DocUploadButton";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

const doc = (over: Partial<HireDocument> = {}): HireDocument => ({
  id: "d1", document_type: "pan_card", document_type_display: "PAN Card", entry_ref: "", file_name: "pan-2026.png",
  file_size: 1200, uploaded_at: "2026-11-14T10:00:00Z", file_url: "https://files.example/pan.png", ...over,
});

function mount(over: Partial<Parameters<typeof DocUploadButton>[0]> = {}) {
  const onUpload = vi.fn();
  const onDelete = vi.fn();
  const utils = render(
    <DocUploadButton documentType="pan_card" label="PAN card" existing={doc()} uploading={false} onUpload={onUpload} onDelete={onDelete} {...over} />,
  );
  return { onUpload, onDelete, ...utils };
}

describe("DocUploadButton > a document that is already uploaded", () => {
  it("still shows the Uploaded badge and the file name", () => {
    mount();
    expect(screen.getByText("Uploaded")).toBeTruthy();
    expect(screen.getByText("pan-2026.png")).toBeTruthy();
  });

  it("shows View as an eye symbol only: no 'View' word, but a name for screen readers and a tooltip", () => {
    mount();
    const view = screen.getByRole("link", { name: "View PAN card" });
    expect(view.textContent).toBe("");                                   // no visible text
    expect(view.querySelector("i.ti-eye")).not.toBeNull();               // the eye symbol
    expect(view.getAttribute("title")).toBe("View PAN card");
    expect(view.getAttribute("href")).toBe("https://files.example/pan.png");
    expect(view.getAttribute("target")).toBe("_blank");
    expect(screen.queryByText("View")).toBeNull();
  });

  it("shows Replace as a symbol only: no 'Replace' word, but a name for screen readers and a tooltip", () => {
    mount();
    const replace = screen.getByRole("button", { name: "Replace PAN card" });
    expect(replace.textContent).toBe("");
    expect(replace.querySelector("i.ti-replace")).not.toBeNull();
    expect(replace.getAttribute("title")).toBe("Replace PAN card");
    expect(screen.queryByText("Replace")).toBeNull();
  });

  it("keeps Delete as its trash symbol", () => {
    const { onDelete } = mount();
    const del = screen.getByRole("button", { name: "Delete" });
    expect(del.querySelector("i.ti-trash")).not.toBeNull();
    fireEvent.click(del);
    expect(onDelete).toHaveBeenCalledWith(doc());
  });

  it("only offers View when the server gave a link to the file", () => {
    mount({ existing: doc({ file_url: undefined }) });
    expect(screen.queryByRole("link", { name: /View/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Replace PAN card" })).toBeTruthy();
  });

  it("Replace opens the file chooser and the chosen file is uploaded for the same document type and entry", () => {
    const click = vi.spyOn(HTMLInputElement.prototype, "click").mockImplementation(() => undefined);
    const { onUpload, container } = mount({ entryRef: "edu-1" });
    fireEvent.click(screen.getByRole("button", { name: "Replace PAN card" }));
    expect(click).toHaveBeenCalledTimes(1);
    const file = new File(["x"], "new.png", { type: "image/png" });
    fireEvent.change(container.querySelector("input[type=file]") as HTMLInputElement, { target: { files: [file] } });
    expect(onUpload).toHaveBeenCalledWith("pan_card", file, "edu-1");
  });

  it("while uploading, Replace is disabled, busy and shows a spinner instead of the symbol", () => {
    mount({ uploading: true });
    const replace = screen.getByRole("button", { name: "Replace PAN card" }) as HTMLButtonElement;
    expect(replace.disabled).toBe(true);
    expect(replace.getAttribute("aria-busy")).toBe("true");
    expect(replace.querySelector("i.ti-loader-2")).not.toBeNull();
    expect(replace.querySelector("i.ti-replace")).toBeNull();
    expect((screen.getByRole("button", { name: "Delete" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("offers no Delete when the caller gave no way to delete", () => {
    mount({ onDelete: undefined });
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });
});

describe("DocUploadButton > a document that is not uploaded yet", () => {
  it("is unchanged: a labelled Upload button", () => {
    mount({ existing: undefined });
    expect(screen.getByRole("button", { name: /Upload PAN card/ })).toBeTruthy();
    expect(screen.queryByText("Uploaded")).toBeNull();
  });

  it("shows 'Uploading…' while the first upload is in progress", () => {
    mount({ existing: undefined, uploading: true });
    expect(screen.getByText(/Uploading/)).toBeTruthy();
  });
});
