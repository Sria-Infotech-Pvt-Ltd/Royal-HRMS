"use client";

// ── Step: Assets ──────────────────────────────────────────────────────────────
// A genuinely repeatable, unbounded list of company assets issued to the
// employee — same shape/convention as ExperienceList.tsx. Optional at hire
// time (assets are normally issued on the actual joining date, not during
// the wizard), so there's no required-field gate on this step.

const ASSET_TYPES: { value: string; label: string }[] = [
  { value: "laptop",       label: "Laptop" },
  { value: "mobile_phone", label: "Mobile Phone" },
  { value: "monitor",      label: "Monitor" },
  { value: "headset",      label: "Headset" },
  { value: "sim_card",     label: "SIM Card" },
];
const CONDITIONS: { value: string; label: string }[] = [
  { value: "new",         label: "New" },
  { value: "good",        label: "Good" },
  { value: "refurbished", label: "Refurbished" },
];

export interface AssetEntry {
  id: string;
  asset_type: string;
  tag_number: string;
  condition: string;
  // "later" (default) means the asset is only planned here and handed over
  // on the actual joining date — only meaningful pre-hire (the Hire
  // wizard's draft, before an employee row even exists). The real
  // onboarding wizard creates a genuine CompanyAsset row immediately on
  // add, which by definition already means "issued", so this is left
  // unset (and the toggle hidden) there.
  issue_when?: "now" | "later";
}

interface Props {
  entries: AssetEntry[];
  onAdd: () => void;
  onFieldChange: (id: string, field: keyof AssetEntry, value: string) => void;
  onRemove: (id: string) => void;
  error: string | null;
  /** Shows the "Issue now / Issue later" toggle — only meaningful for the pre-hire draft (see AssetEntry.issue_when). */
  showIssueToggle?: boolean;
}

export default function AssetsList({ entries, onAdd, onFieldChange, onRemove, error, showIssueToggle = false }: Props) {
  return (
    <div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <p style={{ color: "var(--on-variant)", fontSize: ".85rem", marginBottom: 20 }}>
        Optional at hiring time — assets are usually issued on the actual joining date.
      </p>

      {entries.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".9rem", marginBottom: 16 }}>
          No assets added yet.
        </p>
      )}

      {entries.map(entry => (
        <div key={entry.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
          {/* QA report #54 — with the toggle in its own full-width row, its
              w-fit button pair left most of that row's width empty ("only
              fills half its container"). Placing it as a third grid cell
              alongside Asset/Condition gives it the same proportioned
              width as its siblings instead of a lone narrow control
              floating in a full-width row. */}
          <div className={`form-row ${showIssueToggle ? "cols-3" : "cols-2"}`}>
            <div className="field-group">
              <label className="field-label">Asset</label>
              <select className="field-input field-select" value={entry.asset_type} onChange={e => onFieldChange(entry.id, "asset_type", e.target.value)}>
                <option value="">— Select —</option>
                {ASSET_TYPES.map(a => <option key={a.value} value={a.value}>{a.label}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Condition</label>
              <select className="field-input field-select" value={entry.condition} onChange={e => onFieldChange(entry.id, "condition", e.target.value)}>
                {CONDITIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
              </select>
            </div>
            {showIssueToggle && (
              <div className="field-group">
                <label className="field-label">Issue</label>
                <div className="flex rounded-lg overflow-hidden border border-[var(--outline-v)] w-full">
                  {(["now", "later"] as const).map(v => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => onFieldChange(entry.id, "issue_when", v)}
                      className="flex-1 px-4 py-1.5 text-[12.5px] font-semibold"
                      style={{ background: (entry.issue_when ?? "later") === v ? "var(--primary)" : "var(--surface)", color: (entry.issue_when ?? "later") === v ? "#fff" : "var(--on-bg)" }}
                    >
                      {v === "now" ? "Issue now" : "Issue later"}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {(!showIssueToggle || entry.issue_when === "now") && (
            <div className="field-group" style={{ marginBottom: 12, maxWidth: 260 }}>
              <label className="field-label">Tag / Serial number</label>
              <input className="field-input" value={entry.tag_number} onChange={e => onFieldChange(entry.id, "tag_number", e.target.value)} placeholder="e.g. AIRA-LT-1042" />
            </div>
          )}

          <button className="btn btn-ghost btn-sm" type="button" onClick={() => onRemove(entry.id)}>
            <i className="ti ti-trash" style={{ fontSize: 13 }} /> Remove
          </button>
        </div>
      ))}

      <button className="btn btn-ghost" type="button" onClick={onAdd}>
        <i className="ti ti-plus" /> Issue an Asset
      </button>
    </div>
  );
}
