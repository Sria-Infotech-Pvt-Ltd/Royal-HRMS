"use client";

import { useState } from "react";
import DocPreviewModal from "@/components/DocPreviewModal";
import { LeaveRequest } from "../../leave/_data";
import { ApprovalItem, CorrectionRequest, ExpenseRequest, fmtAmount, fmtSubmitted, initials } from "../_data";
import type { WorkFromHomeRequest } from "@/types/workFromHome";
import type { PayslipQuery } from "@/types/payroll";
import { TypeBadge, StatusChip } from "./Badges";

interface Props {
  item:      ApprovalItem | null;
  onClose:   () => void;
  onApprove: (item: ApprovalItem) => void;
  onReject:  (item: ApprovalItem) => void;
}

// DocPreviewModal decides image-vs-PDF rendering from the file extension in
// `fileName` — without it every attachment (including photo receipts) got
// treated as a PDF and fetched as a blob instead of shown as an <img>.
function fileNameFromUrl(url: string): string {
  try {
    const path = new URL(url, "http://placeholder.local").pathname;
    return decodeURIComponent(path.split("/").pop() || "file");
  } catch {
    return url.split("/").pop() || "file";
  }
}

function isLeave(item: ApprovalItem): item is ApprovalItem & { raw: LeaveRequest } {
  return item.kind === "leave";
}
function isExpense(item: ApprovalItem): item is ApprovalItem & { raw: ExpenseRequest } {
  return item.kind === "expense";
}
function isCorrection(item: ApprovalItem): item is ApprovalItem & { raw: CorrectionRequest } {
  return item.kind === "attendance_correction";
}
function isWfh(item: ApprovalItem): item is ApprovalItem & { raw: WorkFromHomeRequest } {
  return item.kind === "wfh";
}
function isPayslip(item: ApprovalItem): item is ApprovalItem & { raw: PayslipQuery } {
  return item.kind === "payslip";
}

type StageStatus = "approved" | "rejected" | null;

function TimelineDot({ status }: { status: StageStatus }) {
  const cfg = status === "approved"
    ? { bg: "var(--ta-success-soft)", color: "#15803D", icon: "ti-check" }
    : status === "rejected"
    ? { bg: "var(--ta-danger-soft)", color: "#B91C1C", icon: "ti-x" }
    : { bg: "var(--ta-warning-soft)", color: "#B45309", icon: "ti-clock" };
  return (
    <div className="ta-timeline-dot" style={{ background: cfg.bg, color: cfg.color }}>
      <i className={`ti ${cfg.icon}`} />
    </div>
  );
}

function TimelineRow({ label, status, sub }: { label: string; status: StageStatus; sub?: string | null }) {
  return (
    <div className="ta-timeline-item">
      <TimelineDot status={status} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ta-text)" }}>{label}</div>
        <div style={{ fontSize: 12, color: "var(--ta-text-muted)", marginTop: 1 }}>
          {status ? (status === "approved" ? "Approved" : "Rejected") : "Pending"}
          {sub ? ` · ${sub}` : ""}
        </div>
      </div>
    </div>
  );
}

function reasonText(item: ApprovalItem): string {
  if (isExpense(item)) return item.raw.description || "—";
  if (isLeave(item)) return item.raw.reason || "—";
  if (isCorrection(item)) return item.raw.reason || "—";
  if (isWfh(item)) return item.raw.reason || "—";
  return "—";
}

export default function RequestDetailDrawer({ item, onClose, onApprove, onReject }: Props) {
  const [preview, setPreview] = useState<{ name: string; url: string; fileName: string } | null>(null);

  return (
    <>
      <div className={`drawer-overlay ${item ? "open" : ""}`} onClick={onClose} />
      <div className={`drawer ${item ? "open" : ""}`}>
        {item && (
          <>
            <div className="drawer-header">
              <div className="drawer-title">Request Details</div>
              <button className="drawer-close" onClick={onClose} suppressHydrationWarning>
                <i className="ti ti-x" />
              </button>
            </div>

            <div className="drawer-body">
              {/* Employee Information */}
              <div className="ta-drawer-section">
                <div className="ta-drawer-label">Employee Information</div>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 4 }}>
                  <div className="ta-emp-avatar" style={{ width: 42, height: 42, fontSize: 14 }}>
                    {initials(item.employeeName)}
                  </div>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "var(--ta-text)" }}>{item.employeeName}</div>
                    <div style={{ fontSize: 12, color: "var(--ta-text-muted)" }}>
                      {[item.employeeCode !== "—" ? item.employeeCode : null, item.department, item.branch].filter(Boolean).join(" · ") || "—"}
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                  <TypeBadge kind={item.kind} />
                  <StatusChip status={item.displayStatus} />
                </div>
              </div>

              {/* Request Details */}
              <div className="ta-drawer-section">
                <div className="ta-drawer-label">Request Details</div>

                {isLeave(item) && (
                  <>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Leave Type</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.leave_type_display}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Duration</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.duration_display}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Dates</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.detailSecondary}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Total Days</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.total_days}</span></div>
                    {item.raw.lop_days > 0 && (
                      <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>LOP Days</span><span style={{ fontWeight: 600, fontSize: 13, color: "#B45309" }}>{item.raw.lop_days}</span></div>
                    )}
                  </>
                )}

                {isExpense(item) && (
                  <>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Title</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.title}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Category</span><span style={{ fontWeight: 600, fontSize: 13, textTransform: "capitalize" }}>{item.raw.category}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Amount</span><span style={{ fontWeight: 700, fontSize: 14 }}>{fmtAmount(item.raw.amount)}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Expense Date</span><span style={{ fontWeight: 600, fontSize: 13 }}>{fmtSubmitted(item.raw.expense_date)}</span></div>
                  </>
                )}

                {isWfh(item) && (
                  <>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Dates</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.detailSecondary}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Total Days</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.detailTertiary}</span></div>
                    {item.raw.location_label && (
                      <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Location</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.location_label}</span></div>
                    )}
                  </>
                )}

                {isCorrection(item) && (
                  <>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Correction Type</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.detailPrimary}</span></div>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Date</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.detailTertiary}</span></div>
                    {item.detailSecondary.split("  ·  ").map((line, i) => (
                      <div className="ta-drawer-row" key={i}>
                        <span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>{item.raw.punch_type === "BOTH" ? (i === 0 ? "Check-in" : "Check-out") : (item.raw.punch_type === "IN" ? "Check-in" : "Check-out")}</span>
                        <span style={{ fontWeight: 600, fontSize: 13, fontVariantNumeric: "tabular-nums" }}>{line}</span>
                      </div>
                    ))}
                  </>
                )}

                {isPayslip(item) && (
                  <>
                    <div className="ta-drawer-row"><span style={{ color: "var(--ta-text-muted)", fontSize: 13 }}>Raised By</span><span style={{ fontWeight: 600, fontSize: 13 }}>{item.raw.raised_by_name}</span></div>
                    <div style={{ marginTop: 8 }}>
                      <div style={{ color: "var(--ta-text-muted)", fontSize: 13, marginBottom: 4 }}>Query</div>
                      <p style={{ fontSize: 13, color: "var(--ta-text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{item.raw.description}</p>
                    </div>
                    {item.raw.resolution_note && (
                      <div style={{ marginTop: 8 }}>
                        <div style={{ color: "var(--ta-text-muted)", fontSize: 13, marginBottom: 4 }}>Resolution Note</div>
                        <p style={{ fontSize: 13, color: "var(--ta-text)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{item.raw.resolution_note}</p>
                      </div>
                    )}
                  </>
                )}
              </div>

              {/* Reason */}
              <div className="ta-drawer-section">
                <div className="ta-drawer-label">Reason</div>
                <p style={{ fontSize: 13, color: "var(--ta-text)", lineHeight: 1.6 }}>
                  {reasonText(item)}
                </p>
              </div>

              {/* Attachments */}
              {(isLeave(item) && item.raw.document_url) || (isExpense(item) && item.raw.receipts?.length > 0) ? (
                <div className="ta-drawer-section">
                  <div className="ta-drawer-label">Attachments</div>
                  {isLeave(item) && item.raw.document_url && (
                    <div
                      className="ta-attachment"
                      onClick={() => setPreview({ name: "Supporting Document", url: item.raw.document_url as string, fileName: fileNameFromUrl(item.raw.document_url as string) })}
                    >
                      <i className="ti ti-paperclip" />
                      <span style={{ fontSize: 13, fontWeight: 500 }}>Supporting Document</span>
                    </div>
                  )}
                  {isExpense(item) && item.raw.receipts.map((r, idx) => r.url && (
                    <div
                      key={r.id}
                      className="ta-attachment"
                      onClick={() => setPreview({ name: `Receipt ${idx + 1}`, url: r.url as string, fileName: fileNameFromUrl(r.url as string) })}
                    >
                      <i className="ti ti-receipt" />
                      <span style={{ fontSize: 13, fontWeight: 500 }}>Receipt {idx + 1}</span>
                    </div>
                  ))}
                </div>
              ) : null}

              {/* Approval Timeline */}
              <div className="ta-drawer-section">
                <div className="ta-drawer-label">Approval Timeline</div>
                <TimelineRow label="Submitted" status={null} sub={fmtSubmitted(item.submittedAt)} />

                {isLeave(item) && (
                  <>
                    <TimelineRow label="Manager Approval" status={item.raw.l1_status as StageStatus} sub={item.raw.l1_approver_name || undefined} />
                    {item.raw.l2_approver_name && (
                      <TimelineRow label="HR Approval" status={item.raw.l2_status as StageStatus} sub={item.raw.l2_approver_name || undefined} />
                    )}
                  </>
                )}

                {isCorrection(item) && (
                  <>
                    <TimelineRow label="Manager Approval" status={item.raw.l1_status} sub={item.raw.l1_approver_name || undefined} />
                    {item.raw.l2_approver_name && (
                      <TimelineRow label="HR Approval" status={item.raw.l2_status} sub={item.raw.l2_approver_name || undefined} />
                    )}
                  </>
                )}

                {isWfh(item) && (
                  <>
                    <TimelineRow label="Manager Approval" status={item.raw.l1_status} sub={item.raw.l1_approver_name || undefined} />
                    {item.raw.l2_approver_name && (
                      <TimelineRow label="HR Approval" status={item.raw.l2_status} sub={item.raw.l2_approver_name || undefined} />
                    )}
                  </>
                )}

                {isExpense(item) && item.displayStatus !== "pending" && (
                  <TimelineRow label="Decision" status={item.displayStatus === "approved" ? "approved" : "rejected"} />
                )}
              </div>

              {/* Comments */}
              {(() => {
                const comments: { label: string; text: string }[] = [];
                if (isLeave(item) || isCorrection(item) || isWfh(item)) {
                  if (item.raw.l1_remarks) comments.push({ label: item.raw.l1_approver_name || "Manager", text: item.raw.l1_remarks });
                  if (item.raw.l2_remarks) comments.push({ label: item.raw.l2_approver_name || "HR", text: item.raw.l2_remarks });
                }
                if (isExpense(item) && item.raw.remarks) comments.push({ label: "Approver", text: item.raw.remarks });
                if (comments.length === 0) return null;
                return (
                  <div className="ta-drawer-section">
                    <div className="ta-drawer-label">Comments</div>
                    {comments.map((c, i) => (
                      <div key={i} className="ta-comment">
                        <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 3 }}>{c.label}</div>
                        {c.text}
                      </div>
                    ))}
                  </div>
                );
              })()}
            </div>

            {item.canAction && item.displayStatus === "pending" && (
              <div className="drawer-footer">
                <button
                  className="ta-bulk-btn ta-bulk-reject"
                  style={{ padding: "9px 18px" }}
                  onClick={() => onReject(item)}
                  suppressHydrationWarning
                >
                  <i className="ti ti-x" /> Reject
                </button>
                <button
                  className="ta-bulk-btn ta-bulk-approve"
                  style={{ padding: "9px 18px" }}
                  onClick={() => onApprove(item)}
                  suppressHydrationWarning
                >
                  <i className="ti ti-check" /> Approve
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {preview && (
        <DocPreviewModal
          name={preview.name}
          fileName={preview.fileName}
          fileUrl={preview.url}
          onClose={() => setPreview(null)}
        />
      )}
    </>
  );
}
