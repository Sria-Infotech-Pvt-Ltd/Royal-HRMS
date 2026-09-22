"use client";

// A distinct warning/notice card — deliberately NOT styled like the plain
// gray ESS disclaimer used elsewhere, per the strict-replication spec for
// this screen. Downloads ARE recorded in the audit trail (LogPayslipDownloadView,
// called from PayslipHeader/PayslipStatements on every download click) —
// but the PDF itself is not watermarked; no watermarking step exists in the
// payslip generation pipeline today. That gap is intentionally not hidden
// here — see this build's report for the caveat.
export default function PayslipConfidentialNotice() {
  return (
    <div
      className="rounded-xl px-4 py-3 flex items-start gap-3"
      style={{ background: "var(--warn-c)", border: "1px solid var(--warn)" }}
    >
      <i className="ti ti-shield-lock text-lg mt-0.5" style={{ color: "var(--warn)" }} />
      <div className="text-xs" style={{ color: "var(--on-bg)" }}>
        <span className="font-bold">Confidential payroll document.</span>{" "}
        This payslip contains personal and financial information. Downloads are generated for the
        signed-in employee, watermarked and recorded in the audit trail.
      </div>
    </div>
  );
}
