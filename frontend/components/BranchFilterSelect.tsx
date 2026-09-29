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
//
// NOTE: this filters/displays Branch.branch_name (e.g. "Kondapur / T-Hub"),
// not Branch.branch_code — it was previously mislabeled "Company Code(s)",
// which just doesn't match what it actually filters by. Labeled "Location"
// here to match the real data source instead of relabeling the data.
export default function BranchFilterSelect({ branches, value, onChange, locked, lockedBranchName, width = 180 }: Props) {
  if (locked) {
    const label = lockedBranchName || "—";
    return (
      <div style={{ display: "flex", alignItems: "center", gap: 6 }} title="Scoped to your Location">
        <select className="field-input field-select" style={{ width, background: "var(--bg-low)", cursor: "not-allowed" }} value={label} disabled>
          <option value={label}>{label}</option>
        </select>
        <i className="ti ti-lock" style={{ color: "var(--on-variant)", fontSize: 14 }} />
      </div>
    );
  }

  // NOTE: this component is shared with several Attendance tabs that already
  // depend on "" as the "all branches" value/onChange contract — changing it
  // here would silently break those unrelated pages. The Employee Directory
  // itself already normalizes its own "all" filter state to/from "" at the
  // call site (EmployeeToolbar), so its dept/status/branch state is
  // consistently "all" one level up; only this shared subcomponent's own
  // internal DOM value differs, which isn't safe to change without touching
  // every consumer.
  return (
    <select className="field-input field-select" style={{ width }} value={value} onChange={e => onChange(e.target.value)}>
      <option value="">All Locations</option>
      {branches.map(b => <option key={b.id} value={b.branch_name}>{b.branch_name}</option>)}
    </select>
  );
}
