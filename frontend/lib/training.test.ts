import { describe, expect, it } from "vitest";
import {
  canConfirm, courseFormPayload, courseToForm, embedUrl, fileUrl, formatBytes, formatDuration, materialHint,
  materialKindLabel, parseVideoLink, secondsUntilConfirm, uploadError, validateCourse, type Material,
  formatDate, needsVideoLength, parseVideoLength, todayIso, videoLengthSeconds,
} from "./training";

const mat = (over: Partial<Material> = {}): Material => ({
  id: "m1", title: "Intro", description: "", material_type: "video", order: 1, is_required: true, file_format: "mp4",
  file_size: 0, original_name: "", provider: "", embed_id: "", external_url: "", duration_seconds: 100,
  min_view_seconds: 0, allow_manual_completion: false, is_tracked: true, is_archived: false, progress: null, ...over,
});

describe("parseVideoLink", () => {
  it("accepts YouTube, Vimeo and direct files", () => {
    expect(parseVideoLink("https://www.youtube.com/watch?v=dQw4w9WgXcQ")).toEqual({ provider: "youtube", id: "dQw4w9WgXcQ" });
    expect(parseVideoLink("https://youtu.be/dQw4w9WgXcQ?t=3")).toEqual({ provider: "youtube", id: "dQw4w9WgXcQ" });
    expect(parseVideoLink("https://www.youtube.com/shorts/dQw4w9WgXcQ")).toEqual({ provider: "youtube", id: "dQw4w9WgXcQ" });
    expect(parseVideoLink("https://vimeo.com/123456")).toEqual({ provider: "vimeo", id: "123456" });
    expect(parseVideoLink("https://cdn.example.com/a/intro.mp4")).toEqual({ provider: "direct", id: "" });
  });
  it("rejects unsafe or unsupported links", () => {
    for (const bad of ["http://youtube.com/watch?v=dQw4w9WgXcQ", "javascript:alert(1)", "https://localhost/a.mp4",
      "https://10.0.0.1/a.mp4", "https://u:p@example.com/a.mp4", "https://example.com/page", "not a url",
      "https://www.youtube.com/watch?v=bad"]) {
      expect("error" in parseVideoLink(bad), bad).toBe(true);
    }
  });
});

describe("embedUrl / fileUrl", () => {
  it("builds privacy-friendly embeds", () => {
    expect(embedUrl({ provider: "youtube", embed_id: "dQw4w9WgXcQ", external_url: "" }))
      .toContain("youtube-nocookie.com/embed/dQw4w9WgXcQ?enablejsapi=1");
    expect(embedUrl({ provider: "vimeo", embed_id: "9", external_url: "" })).toBe("https://player.vimeo.com/video/9");
    expect(embedUrl({ provider: "direct", embed_id: "", external_url: "https://x.com/a.mp4" })).toBe("https://x.com/a.mp4");
    expect(fileUrl("abc")).toBe("/api/training/materials/abc/file/");
  });
});

describe("material progress helpers", () => {
  it("never completes from opening alone", () => {
    expect(canConfirm(mat({ material_type: "document", is_tracked: false }))).toBe(false);
    const opened = { opened_at: "2026-11-11T10:00:00Z", watched_seconds: 0, last_position_seconds: 0,
                     duration_seconds: null, completed_at: null, completion_method: "" as const };
    expect(canConfirm(mat({ material_type: "document", is_tracked: false, progress: opened }))).toBe(true);
    expect(canConfirm(mat({ progress: opened }))).toBe(false);                               // tracked video
    expect(canConfirm(mat({ material_type: "external_video", provider: "vimeo", is_tracked: false, progress: opened })))
      .toBe(false);
    expect(canConfirm(mat({ material_type: "external_video", provider: "vimeo", is_tracked: false,
                            allow_manual_completion: true, progress: opened }))).toBe(true);
  });
  it("counts down the minimum reading time", () => {
    const m = mat({ material_type: "document", min_view_seconds: 60, progress: {
      opened_at: "2026-11-11T10:00:00Z", watched_seconds: 0, last_position_seconds: 0, duration_seconds: null,
      completed_at: null, completion_method: "" } });
    expect(secondsUntilConfirm(m, Date.parse("2026-11-11T10:00:20Z"))).toBe(40);
    expect(secondsUntilConfirm(m, Date.parse("2026-11-11T10:02:00Z"))).toBe(0);
  });
  it("describes what is left", () => {
    expect(materialHint(mat({ progress: { opened_at: "x", watched_seconds: 45, last_position_seconds: 45,
      duration_seconds: 100, completed_at: null, completion_method: "" } }))).toBe("Watched 45% — completes at 90%");
    expect(materialHint(mat({ material_type: "external_video", provider: "vimeo", is_tracked: false })))
      .toMatch(/ask HR/);
    expect(materialKindLabel({ material_type: "document", file_format: "pptx", provider: "" })).toBe("PPTX");
  });
});

describe("formatting", () => {
  it("formats durations and sizes", () => {
    expect(formatDuration(3725)).toBe("1h 2m");
    expect(formatDuration(90)).toBe("1m 30s");
    expect(formatDuration(0)).toBe("");
    expect(formatBytes(2.5 * 1024 * 1024)).toBe("2.5 MB");
  });
});

describe("uploads and course form", () => {
  it("checks type and size before uploading", () => {
    const f = (name: string, size: number) => ({ name, size } as File);
    expect(uploadError(f("a.pdf", 10), "document", 25)).toBe("");
    expect(uploadError(f("a.exe", 10), "document", 25)).toMatch(/PDF/);
    expect(uploadError(f("v.mov", 10), "video", 200)).toMatch(/MP4/);
    expect(uploadError(f("v.mp4", 300 * 1024 * 1024), "video", 200)).toMatch(/200 MB/);
    expect(uploadError(null, "video", 200)).toBe("Choose a video.");
  });
  it("validates and builds the payload", () => {
    const form = { ...courseToForm(null), title: "Safety", start_date: "2026-12-10", deadline: "2026-12-01" };
    expect(Object.keys(validateCourse(form))).toEqual(["deadline"]);
    expect(validateCourse({ ...form, deadline: "" })).toEqual({});
    expect(validateCourse({ ...form, deadline: "", auto_assign_new_joiners: true, new_joiner_deadline_days: "400" }))
      .toHaveProperty("new_joiner_deadline_days");
    expect(courseFormPayload({ ...form, assessment: "a1" }, false)).not.toHaveProperty("assessment");
    expect(courseFormPayload({ ...form, assessment: "" }, true).assessment).toBeNull();
  });
});

describe("audit fixes", () => {
  it("optional video watching needs a linked assessment (course setting)", () => {
    const form = { ...courseToForm(null), title: "Safety", videos_optional: true };
    expect(validateCourse(form)).toHaveProperty("videos_optional");
    expect(validateCourse({ ...form, assessment: "a1" })).toEqual({});
    expect(courseFormPayload({ ...form, assessment: "a1" }, true).videos_optional).toBe(true);
    expect(courseToForm(null).videos_optional).toBe(false);
  });

  it("video length is required for tracked videos and entered as minutes + seconds (C-2)", () => {
    expect(needsVideoLength("video", null)).toBe(true);
    expect(needsVideoLength("external_video", "youtube")).toBe(true);
    expect(needsVideoLength("external_video", "direct")).toBe(true);
    expect(needsVideoLength("external_video", "vimeo")).toBe(false);
    expect(needsVideoLength("document", null)).toBe(false);
    expect(videoLengthSeconds("12", "30")).toBe(750);
    expect(videoLengthSeconds("", "45")).toBe(45);
    expect(videoLengthSeconds("1", "75")).toBe(0);
    expect(parseVideoLength("12:30")).toBe(750);
    expect(parseVideoLength("5")).toBe(300);
    expect(parseVideoLength("0")).toBeNull();
    expect(parseVideoLength("abc")).toBeNull();
    expect(materialHint(mat({ duration_seconds: null }))).toBe("Video length not set — ask HR");
  });

  it("formats start dates and today's date", () => {
    expect(formatDate("2026-12-05")).toBe("05 Dec 2026");
    expect(formatDate(null)).toBe("");
    expect(todayIso(new Date(2026, 0, 7))).toBe("2026-01-07");
  });
});
