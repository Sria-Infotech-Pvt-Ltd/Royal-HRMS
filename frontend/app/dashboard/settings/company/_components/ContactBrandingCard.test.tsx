// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import ContactBrandingCard from "./ContactBrandingCard";
import { EMPTY_COMPANY, validateCompany } from "../_data";
import type { CompanyData } from "@/types/company";

vi.mock("./ProfileCard", () => ({
  default: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

function mount(over: Partial<CompanyData> = {}, extra: { canEdit?: boolean; error?: string } = {}) {
  const onFieldChange = vi.fn();
  render(
    <ContactBrandingCard
      form={{ ...EMPTY_COMPANY, ...over }}
      errors={extra.error ? { portal_url: extra.error } : {}}
      canEdit={extra.canEdit ?? true}
      onFieldChange={onFieldChange}
      displayLogo={null}
      fileRef={{ current: null }}
      onLogoChange={vi.fn()}
      onLogoRemove={vi.fn()}
      collapsed={false}
      onToggleCollapse={vi.fn()}
    />,
  );
  return onFieldChange;
}

afterEach(cleanup);

describe("Employee Portal URL in Company Settings", () => {
  it("shows an editable field with the saved value and the example address", () => {
    mount({ portal_url: "https://aira.nxsys.in" });
    const input = screen.getByLabelText("Employee Portal URL") as HTMLInputElement;
    expect(input.value).toBe("https://aira.nxsys.in");
    expect(input.placeholder).toBe("https://aira.nxsys.in");
    expect(input.disabled).toBe(false);
  });

  it("reports what the administrator types", () => {
    const onFieldChange = mount();
    fireEvent.change(screen.getByLabelText("Employee Portal URL"), { target: { value: "https://aira.nxsys.in" } });
    expect(onFieldChange).toHaveBeenCalledWith("portal_url", "https://aira.nxsys.in");
  });

  it("is read-only without the settings.edit permission", () => {
    mount({ portal_url: "https://aira.nxsys.in" }, { canEdit: false });
    expect((screen.getByLabelText("Employee Portal URL") as HTMLInputElement).disabled).toBe(true);
  });

  it("shows the error message instead of the help text", () => {
    mount({ portal_url: "http://" }, { error: "The portal URL must use https://." });
    expect(screen.getByText("The portal URL must use https://.")).toBeTruthy();
    expect(screen.queryByText(/The public address employees open/)).toBeNull();
  });
});

describe("validateCompany portal_url", () => {
  it("flags a malformed portal URL on both a full save and a draft save", () => {
    expect(validateCompany({ ...EMPTY_COMPANY, portal_url: "http://" }, true).portal_url).toBeTruthy();
    expect(validateCompany({ ...EMPTY_COMPANY, portal_url: "http://" }).portal_url).toBeTruthy();
  });

  it("accepts the production address and a blank value", () => {
    expect(validateCompany({ ...EMPTY_COMPANY, portal_url: "https://aira.nxsys.in" }, true).portal_url).toBeUndefined();
    expect(validateCompany({ ...EMPTY_COMPANY, portal_url: "" }, true).portal_url).toBeUndefined();
  });
});
