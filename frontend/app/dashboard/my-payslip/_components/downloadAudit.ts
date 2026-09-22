import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// Fire-and-forget audit log call — backs the "Downloads are ... recorded in
// the audit trail" notice on the ESS Payslips screen (see
// LogPayslipDownloadView in apps/payroll/views/payslips.py). Never blocks or
// cancels the actual <a> download navigation, so a logging failure never
// stops the employee from getting their payslip.
export function logPayslipDownload(payslipId: string): void {
  clientApi.post(API.payroll.logPayslipDownload(payslipId)).catch(() => {});
}
