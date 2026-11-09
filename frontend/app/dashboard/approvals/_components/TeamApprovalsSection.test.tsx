import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

// The Team Approvals section asks for the attendance-corrections list only for someone who holds attendance.view.
let allowed: Set<string>;
let requested: string[];

vi.mock("@/hooks/usePermission", () => ({ usePermission: (code: string) => allowed.has(code) }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string | null) => {
    if (url) requested.push(url);
    return { data: null, loading: false, error: null, status: null, refetch: () => {} };
  },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("@/components/ToastProvider", () => ({ useToast: () => ({ showToast: () => {} }) }));
vi.mock("@/components/DialogProvider", () => ({ confirmDialog: async () => false }));

import TeamApprovalsSection from "./TeamApprovalsSection";

const corrections = () => requested.some(url => url.startsWith("/attendance/corrections/"));

beforeEach(() => {
  requested = [];
  allowed = new Set();
});

describe("TeamApprovalsSection corrections request", () => {
  it("is not made without attendance.view", () => {
    allowed = new Set(["leave.approve"]);
    renderToStaticMarkup(<TeamApprovalsSection />);
    expect(corrections()).toBe(false);
  });

  it("is made with attendance.view", () => {
    allowed = new Set(["attendance.view"]);
    renderToStaticMarkup(<TeamApprovalsSection />);
    expect(corrections()).toBe(true);
  });

  it("does not stop the other workflow lists from loading", () => {
    allowed = new Set(["leave.approve"]);
    renderToStaticMarkup(<TeamApprovalsSection />);
    expect(requested.some(url => url.startsWith("/leave/requests/"))).toBe(true);
  });
});
