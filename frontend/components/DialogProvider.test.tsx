import { describe, expect, it } from "vitest";
import { confirmDialog, promptDialog } from "./DialogProvider";

// Without the provider mounted (as in a plain unit test) the dialogs answer "no" instead of falling back to a native dialog.
describe("dialog functions without a provider", () => {
  it("confirmDialog resolves false", async () => {
    expect(await confirmDialog("Delete it?")).toBe(false);
  });
  it("promptDialog resolves null", async () => {
    expect(await promptDialog({ title: "Link", inputLabel: "URL" })).toBeNull();
  });
});
