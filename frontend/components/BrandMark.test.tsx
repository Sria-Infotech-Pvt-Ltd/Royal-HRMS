// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({ data: null as { company_name: string | null; logo_url: string | null } | null, loading: false }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: state.data, loading: state.loading }) }));

import BrandLogo from "./BrandLogo";
import BrandMark from "./BrandMark";
import PoweredBy from "./PoweredBy";

beforeEach(() => { state.data = null; state.loading = false; });
afterEach(cleanup);

describe("BrandMark (the top-left corner)", () => {
  it("shows the company's logo once one is set up in Company Info", () => {
    state.data = { company_name: "Sria Infotech", logo_url: "https://files.example/sria.png" };
    const { container } = render(<BrandMark />);
    const logo = screen.getByRole("img", { name: "Sria Infotech" });
    expect(logo.getAttribute("src")).toBe("https://files.example/sria.png");
    expect(container.querySelector(".sq")).toBeNull();
  });

  it("shows the AIRA mark when the company has no logo", () => {
    state.data = { company_name: "Sria Infotech", logo_url: null };
    const { container } = render(<BrandMark />);
    expect(container.querySelector(".sq svg")).toBeTruthy();
    expect(container.textContent).toContain("AIRA");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("holds its place, hidden, while the first answer loads, so the wrong logo never flashes", () => {
    state.loading = true;
    const { container } = render(<BrandMark />);
    const corner = container.querySelector(".brandmark") as HTMLElement;
    expect(corner.style.visibility).toBe("hidden");
    expect(corner.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("BrandLogo (the sign-up pages)", () => {
  it("is the company logo when there is one, the AIRA mark when there is not", () => {
    state.data = { company_name: "Sria Infotech", logo_url: "https://files.example/sria.png" };
    const { rerender } = render(<BrandLogo height={34} />);
    expect(screen.getByRole("img", { name: "Sria Infotech" }).getAttribute("src")).toBe("https://files.example/sria.png");
    state.data = { company_name: null, logo_url: null };
    rerender(<BrandLogo height={34} />);
    expect(screen.getByRole("img", { name: "AIRA" }).getAttribute("src")).toBe("/logo-icon.png");
  });
});

describe("PoweredBy", () => {
  it("names the product and shows its mark", () => {
    const { container } = render(<PoweredBy />);
    expect(container.textContent).toContain("Powered by AIRA");
    expect(container.querySelector("img")?.getAttribute("src")).toBe("/logo-icon.png");
  });
});
