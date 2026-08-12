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
  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-user" /> Employee Details</span>
      </div>
      <div className="card-body">
        <div className="form-row cols-2">
          <ReadField label="Employee Name" value={r.employee_name} />
          <ReadField label="Employee Code" value={r.employee_code} />
        </div>
        <div className="form-row cols-2">
          <ReadField label="Department" value={r.employee_department} />
          <ReadField label="Designation" value={r.employee_designation} />
        </div>
        <ReadField label="Reporting Manager" value={r.reporting_manager ? `${r.reporting_manager.name} (${r.reporting_manager.id})` : "Not assigned"} />
      </div>
    </div>
  );
}
