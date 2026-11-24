import { useT } from "@/hooks/useI18n";
import type { SeparationRequest } from "@/types/separation";

function ReadField({ label, value }: { label: string; value: string }) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      <input className="field-input" value={value || "—"} disabled />
    </div>
  );
}

export default function EmployeeDetailsSection({ r }: { r: SeparationRequest }) {
  const t = useT();
  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-user" /> {t("Employee Details")}</span>
      </div>
      <div className="card-body">
        <div className="form-row cols-2">
          <ReadField label={t("Employee Name")} value={r.employee_name} />
          <ReadField label={t("Employee Code")} value={r.employee_code} />
        </div>
        <div className="form-row cols-2">
          <ReadField label={t("Department")} value={r.employee_department} />
          <ReadField label={t("Designation")} value={r.employee_designation} />
        </div>
        <ReadField label={t("Reporting Manager")} value={r.reporting_manager ? `${r.reporting_manager.name} (${r.reporting_manager.id})` : t("Not assigned")} />
      </div>
    </div>
  );
}
