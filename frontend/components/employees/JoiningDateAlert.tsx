"use client";

interface Props {
  /** Employees with no joining date (Employment Stage "Unknown"). */
  missingCount: number;
  onShow: () => void;
}

/** Tells HR that some employees have no joining date: they are left out of attendance and payroll until it is corrected. */
export default function JoiningDateAlert({ missingCount, onShow }: Props) {
  if (missingCount <= 0) return null;
  const noun = missingCount === 1 ? "employee has" : "employees have";
  return (
    <div className="alert alert-warn" role="status" style={{ margin: "0 0 12px", display: "flex", alignItems: "center", gap: 10 }}>
      <i className="ti ti-calendar-exclamation" />
      <span style={{ flex: 1 }}>
        {missingCount} {noun} no joining date. They are left out of attendance and payroll until HR corrects it.
      </span>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onShow} suppressHydrationWarning>Show them</button>
    </div>
  );
}
