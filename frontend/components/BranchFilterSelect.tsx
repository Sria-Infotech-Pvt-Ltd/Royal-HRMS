"use client";

interface BranchOption {
  id:          number;
  branch_name: string;
}

interface Props {
  branches:  BranchOption[];
  value:     string;
  onChange:  (value: string) => void;
  locked:    boolean;
  lockedBranchName?: string;
  width?:    number;
}

// Renders either a full "All Branches" dropdown (system_admin) or a single,
// disabled option locked to the user's own branch (hr_admin) — the branch is
// already enforced server-side, this just keeps the UI honest about it.
export default function BranchFilterSelect({ branches, value, onChange, locked, lockedBranchName, width = 180 }: Props) {
  if (locked) {
    const label = lockedBranchName || "—";
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6 }} title="Scoped to your Company Code">
        <select className="field-input field-select" style={{ width, background: "var(--bg-low)", cursor: "not-allowed" }} value={label} disabled>
          <option value={label}>{label}</option>
        </select>
        <i className="ti ti-lock" style={{ color: "var(--on-variant)", fontSize: 14 }} />
      </div>
    );
  }

  return (
    <select className="field-input field-select" style={{ width }} value={value} onChange={e => onChange(e.target.value)}>
      <option value="">All Company Codes</option>
      {branches.map(b => <option key={b.id} value={b.branch_name}>{b.branch_name}</option>)}
    </select>
  );
}
