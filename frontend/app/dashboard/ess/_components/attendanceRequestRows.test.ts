import { describe, expect, it } from "vitest";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { MyCorrectionRequest } from "../../my-requests/_data";
import { buildAttendanceRequestRows, correctionTitle } from "./attendanceRequestRows";

const correction = (over: Partial<MyCorrectionRequest> = {}): MyCorrectionRequest => ({
  id: "c1", date: "2026-11-10", punch_type: "IN", original_in: null, original_out: null, requested_in: "09:30", requested_out: null,
  reason: "Forgot to punch", status: "pending", l1_approver_name: "Asha", l1_status: null, l1_remarks: "", l2_approver_name: null,
  l2_status: null, l2_remarks: "", reviewed_by: null, reviewed_at: null, created_at: "2026-11-10T10:00:00Z", ...over,
});

const wfh = (over: Partial<WorkFromHomeRequest> = {}): WorkFromHomeRequest => ({
  id: "abcdef123456", start_date: "2026-11-20", end_date: "2026-11-22", reason: "", location_label: "Home", latitude: "17.1", longitude: "78.1",
  status: "pending", employee_name: "Test", employee_code: "10000001", employee_dept: "Web", employee_branch: "Sria",
  l1_approver_name: "Asha", l1_status: null, l1_remarks: "", l1_actioned_at: null, l2_approver_name: "", l2_status: null, l2_remarks: "",
  l2_actioned_at: null, created_at: "2026-11-12T10:00:00Z", can_approve: false, can_cancel: true, ...over,
});

describe("buildAttendanceRequestRows", () => {
  it("merges corrections and work-from-home requests, newest first", () => {
    const rows = buildAttendanceRequestRows(
      [correction({ id: "old", created_at: "2026-11-01T10:00:00Z" }), correction({ id: "new", created_at: "2026-11-13T10:00:00Z" })],
      [wfh({ id: "mid-wfh", created_at: "2026-11-12T10:00:00Z" })],
      10,
    );
    expect(rows.map(row => row.key)).toEqual(["correction:new", "wfh:mid-wfh", "correction:old"]);
  });

  it("keeps only the newest `limit` rows", () => {
    const wfhRequests = [1, 2, 3, 4].map(n => wfh({ id: `w${n}`, created_at: `2026-11-0${n}T10:00:00Z` }));
    expect(buildAttendanceRequestRows([], wfhRequests, 2).map(row => row.key)).toEqual(["wfh:w4", "wfh:w3"]);
  });

  it("each row carries the request behind it, so it can open its own detail dialog", () => {
    const [first, second] = buildAttendanceRequestRows([correction({ created_at: "2026-11-13T10:00:00Z" })], [wfh()], 5);
    expect(first.correction?.id).toBe("c1");
    expect(first.wfh).toBeUndefined();
    expect(second.wfh?.id).toBe("abcdef123456");
    expect(second.correction).toBeUndefined();
  });

  it("describes a work-from-home request with its dates, status and approver", () => {
    const [pending] = buildAttendanceRequestRows([], [wfh()], 5);
    expect(pending).toMatchObject({ title: "Work from home · Home", statusLabel: "PENDING", isApproved: false });
    expect(pending.detail).toContain("3 days");
    expect(pending.detail).toContain("Pending");

    const [approved] = buildAttendanceRequestRows([], [wfh({ status: "approved", l1_status: "approved", l1_approver_name: "Asha" })], 5);
    expect(approved).toMatchObject({ statusLabel: "APPROVED", isApproved: true });
    expect(approved.detail).toContain("Approved by Asha");
  });

  it("treats a second-level pending request as pending", () => {
    expect(buildAttendanceRequestRows([], [wfh({ status: "l2_pending" })], 5)[0].statusLabel).toBe("PENDING");
  });

  it("falls back to a plain title when the request has no location label", () => {
    expect(buildAttendanceRequestRows([], [wfh({ location_label: "" })], 5)[0].title).toBe("Work from home");
  });

  it("shows corrections exactly as before", () => {
    const [row] = buildAttendanceRequestRows([correction({ status: "approved", l2_approver_name: "Hari" })], [], 5);
    expect(row).toMatchObject({ title: "10 November correction", statusLabel: "APPROVED", isApproved: true });
    expect(row.detail).toBe("Approved by Hari · View details");
  });

  it("returns nothing when there is nothing", () => {
    expect(buildAttendanceRequestRows([], [], 5)).toEqual([]);
  });

  it("names a correction with an unreadable date plainly", () => {
    expect(correctionTitle("not-a-date")).toBe("Correction");
  });
});
