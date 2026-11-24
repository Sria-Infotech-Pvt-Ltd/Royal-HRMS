"use client";

// Shown right after a hire is completed: confirms the employee, says whether the welcome email went out, and tells HR
// exactly what to do about Face ID (and what the new hire has been told), using the same wording as the email.

import Modal from "@/components/Modal";
import type { FaceIdHireSummary } from "@/types/faceId";
import { useT } from "@/hooks/useI18n";

interface Props {
  employeeName: string;
  employeeCode: string;
  faceId: FaceIdHireSummary;
  /** Who the new hire reports to: `source` "none" means nobody could be resolved and HR must assign one. */
  reportingManager?: { name: string | null; source: string } | null;
  onDone: () => void;
}

export default function HireCompletionPanel({ employeeName, employeeCode, faceId, reportingManager, onDone }: Props) {
  const t = useT();
  return (
    <Modal
      title={<div className="text-[18px] font-bold">{t("Employee")} <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{t("hired")}</span></div>}
      onClose={onDone}
      maxWidth={640}
      footer={<button className="btn btn-filled" type="button" onClick={onDone}>{t("Done")}</button>}
    >
      <div style={{ display: "grid", gap: 14 }}>
        <div className="alert alert-success" role="status">
          <i className="ti ti-circle-check" /> <b>{employeeName}</b>{employeeCode ? ` (${employeeCode})` : ""} {t("has been hired. A welcome email with the login details has been sent.")}
        </div>

        {reportingManager && (
          reportingManager.name ? (
            <div style={{ fontSize: 13 }}>
              <b>{t("Reports to:")}</b> {reportingManager.name}
              {reportingManager.source === "org_chart" ? ` ${t("(the head of their org unit)")}` : ""}
            </div>
          ) : (
            <div className="alert alert-warning" role="alert">
              <i className="ti ti-alert-triangle" /> {t("No reporting manager could be found for {name}, so leave and other requests have nobody to go to until one is assigned.", { name: employeeName.split(" ")[0] || t("this employee") })} {t("Use")} <b>{t("Assign managers")}</b> {t("in the Employee Directory.")}
            </div>
          )
        )}

        <section aria-label={t("Face ID")}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 6 }}><i className="ti ti-face-id" style={{ marginRight: 6 }} />{t("Face ID")}</h3>
          {faceId.is_mandatory ? (
            <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
              <div><b>{t("Next step for you:")}</b> {faceId.hr_next_step}</div>
              <div><b>{t("What {name} is told:", { name: employeeName.split(" ")[0] || t("the new hire") })}</b> {faceId.employee_message}</div>
              {faceId.fallback_active && (
                <div className="alert alert-info">
                  <i className="ti ti-info-circle" /> {t("Until it is done they can clock in from the office without a face match")}
                  {faceId.fallback_until ? ` ${t("(until {date})", { date: faceId.fallback_until })}` : ""}. {t("Those punches are flagged for HR.")}
                </div>
              )}
              {faceId.registration_mode !== "self_service" && (
                <a href="/dashboard/face-id-registrations" style={{ color: "var(--primary)", fontWeight: 600 }}>{t("Open Face ID Registrations")}</a>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 13, color: "var(--on-variant)" }}>{t("Face ID is not required for clock-in at the moment. Nothing to do.")}</div>
          )}
        </section>
      </div>
    </Modal>
  );
}
