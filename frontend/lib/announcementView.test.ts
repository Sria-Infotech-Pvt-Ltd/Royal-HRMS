import { describe, expect, it } from "vitest";
import { audienceLabel, categoryLabel, viewState, type AnnouncementDetail } from "./announcementView";

const ann: AnnouncementDetail = {
  id: 7, title: "Company Anniversary", body: "Dear Team,\n\nWe are completing 10 years!\n- Cake\n- Lunch",
  category: "celebration", visibility: "branch", target_department_name: null, target_branch_name: "Suryapet",
  is_pinned: false, posted_by_name: "Jane Smith", posted_by_role: "HR Admin",
  created_at: "2026-10-27T10:00:00Z", updated_at: "2026-10-27T10:00:00Z",
};

describe("viewState", () => {
  it("shows loading until the full post arrives", () => {
    expect(viewState(null, true, null, null)).toEqual({ kind: "loading" });
  });

  it("shows the full post body (not a preview) once loaded", () => {
    const v = viewState(ann, false, null, null);
    expect(v.kind).toBe("ready");
    if (v.kind === "ready") expect(v.ann.body).toBe(ann.body);
  });

  it("treats 404 / 403 as unavailable and reveals nothing", () => {
    expect(viewState(null, false, "Not found.", 404)).toEqual({ kind: "unavailable" });
    expect(viewState(null, false, "Forbidden", 403)).toEqual({ kind: "unavailable" });
  });

  it("other failures show a retryable error", () => {
    expect(viewState(null, false, "Request failed.", 500))
      .toEqual({ kind: "error", message: "Couldn't load this announcement. Please try again." });
    expect(viewState(null, false, "Network Error", null).kind).toBe("error");
  });
});

describe("labels", () => {
  it("describes who the post is for", () => {
    expect(audienceLabel(ann)).toBe("Branch: Suryapet");
    expect(audienceLabel({ visibility: "department", target_department_name: "HR", target_branch_name: null })).toBe("Department: HR");
    expect(audienceLabel({ visibility: "all", target_department_name: null, target_branch_name: null })).toBe("All employees");
  });

  it("capitalises the category", () => {
    expect(categoryLabel("celebration")).toBe("Celebration");
    expect(categoryLabel("")).toBe("");
  });
});
