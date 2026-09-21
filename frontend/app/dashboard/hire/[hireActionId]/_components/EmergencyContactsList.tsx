"use client";

// Repeatable Emergency Contacts card list for Hire wizard Step 1 — matches
// the reference layout (bordered card per contact, Primary checkbox, Remove
// link, "+ Add emergency contact" dashed button) rather than the single
// fixed set of emergency_* fields the shared onboarding wizard uses
// elsewhere. Only the entry marked Primary is ever applied to the real
// EmployeeProfile record at Stage 2 (that model has one emergency-contact
// slot, not a list) — HireWizardClient keeps form.emergency_* in sync with
// whichever entry is primary; every entry is still saved in the draft.

export interface EmergencyContactEntry {
  id: string;
  name: string;
  relationship: string;
  phone: string;
  alternate_phone: string;
  email: string;
  address: string;
  is_primary: boolean;
}

const RELATIONSHIPS = ["Spouse", "Parent", "Sibling", "Child", "Friend", "Other"];

interface Props {
  entries: EmergencyContactEntry[];
  onAdd: () => void;
  onFieldChange: (id: string, field: keyof EmergencyContactEntry, value: string | boolean) => void;
  onRemove: (id: string) => void;
  onSetPrimary: (id: string) => void;
}

export default function EmergencyContactsList({ entries, onAdd, onFieldChange, onRemove, onSetPrimary }: Props) {
  return (
    <div>
      <div className="sechead">EMERGENCY CONTACTS</div>
      <p className="hint" style={{ marginBottom: 10 }}>Add at least two, in case the first is unreachable.</p>

      <div className="rlist" style={{ marginBottom: 12 }}>
        {entries.map((c, i) => (
          <div key={c.id} className="rrow">
            <div className="rrow-h">
              <span className="etag">EMERGENCY CONTACT {i + 1}</span>
              <label className="chkline">
                <input type="checkbox" checked={c.is_primary} onChange={() => onSetPrimary(c.id)} />
                Primary
              </label>
              {entries.length > 1 && (
                <button type="button" onClick={() => onRemove(c.id)} className="mini">Remove</button>
              )}
            </div>

            <div className="g3" style={{ marginBottom: 10 }}>
              <div className="f">
                <label>Name</label>
                <input value={c.name} onChange={e => onFieldChange(c.id, "name", e.target.value)} placeholder="Full name" className="finput" />
              </div>
              <div className="f">
                <label>Relationship</label>
                <select value={c.relationship} onChange={e => onFieldChange(c.id, "relationship", e.target.value)} className="finput" style={{ cursor: "pointer" }}>
                  <option value="">Select</option>
                  {RELATIONSHIPS.map(r => <option key={r} value={r}>{r}</option>)}
                </select>
              </div>
              <div className="f">
                <label>Phone</label>
                <input value={c.phone} onChange={e => onFieldChange(c.id, "phone", e.target.value)} placeholder="+91 90000 00000" className="finput" />
              </div>
            </div>
            <div className="g3">
              <div className="f">
                <label>Alternate phone <span className="tag">OPTIONAL</span></label>
                <input value={c.alternate_phone} onChange={e => onFieldChange(c.id, "alternate_phone", e.target.value)} placeholder="Optional" className="finput" />
              </div>
              <div className="f">
                <label>Email <span className="tag">OPTIONAL</span></label>
                <input type="email" value={c.email} onChange={e => onFieldChange(c.id, "email", e.target.value)} placeholder="Optional" className="finput" />
              </div>
              <div className="f">
                <label>Address <span className="tag">OPTIONAL</span></label>
                <input value={c.address} onChange={e => onFieldChange(c.id, "address", e.target.value)} placeholder="Optional" className="finput" />
              </div>
            </div>
          </div>
        ))}
      </div>

      <button type="button" onClick={onAdd} className="add">+ Add emergency contact</button>
    </div>
  );
}
