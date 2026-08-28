"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import DocPreviewModal from "@/components/DocPreviewModal";
import Modal from "@/components/Modal";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";

interface OnboardingDocument { id: number; document_type_display: string; file_name: string; file_url?: string; file_size?: number; }

interface ProfileData {
  date_of_birth?: string; gender?: string; marital_status?: string;
  father_name?: string; blood_group?: string;
  current_address?: string; permanent_address?: string;
  highest_qualification?: string; institution?: string;
  year_of_passing?: number; specialization?: string;
  total_experience_years?: string; previous_employer?: string;
  previous_designation?: string;
  account_number?: string; ifsc_code?: string; bank_name?: string;
  bank_branch_name?: string; account_holder_name?: string; account_type?: string;
  emergency_name?: string; emergency_relationship?: string;
  emergency_phone?: string; emergency_email?: string;
  uan_number?: string; name_as_per_aadhar?: string; pan_number?: string;
}

export interface ApprovalUser {
  id: string; full_name: string; email: string; phone: string;
  department: string; designation: string; branch: string;
  role_name: string; role_display: string; employee_id: string;
  onboarding_status: string; date_joined: string;
  candidate_id?: number | null;
  profile: ProfileData | null;
  documents: OnboardingDocument[];
}

interface AssessmentOption { id: string; title: string; }

interface Props {
  user:            ApprovalUser;
  remarks:         string;
  acting:          boolean;
  actionErr:       string | null;
  onRemarksChange: (v: string) => void;
  onAction:        (userId: string, decision: "approve" | "reject", extras?: { position?: string; assessmentId?: string; uanNumber?: string; aadharName?: string; panNumber?: string }) => void;
  onClose:         () => void;
}

const PAN_RE = /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/;

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: ".3rem 0", fontSize: ".85rem", borderBottom: "1px solid var(--outline-v)" }}>
      <span style={{ color: "var(--on-variant)" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <div style={{ fontWeight: 700, fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--on-variant)", marginBottom: ".5rem" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

export default function OnboardingDrawer({ user, remarks, acting, actionErr, onRemarksChange, onAction, onClose }: Props) {
  const [showAssign, setShowAssign] = useState(false);
  const [orgUnitId,   setOrgUnitId]   = useState("");
  const [selPosition, setSelPosition] = useState("");
  const { units, positionsForUnit, resolveDepartmentName, loading: positionsLoading } = useOrgUnitsAndPositions();
  const positionOptions  = positionsForUnit(orgUnitId, /* vacantOnly */ true);
  const selectedPosition = positionOptions.find(p => p.id === selPosition);
  const derivedDepartmentName = resolveDepartmentName(orgUnitId);
  const [assignErr,      setAssignErr]      = useState("");
  const [previewDoc,     setPreviewDoc]     = useState<OnboardingDocument | null>(null);
  const [showAssessment, setShowAssessment] = useState(false);
  const [assessments,    setAssessments]    = useState<AssessmentOption[]>([]);
  const [loadAssess,     setLoadAssess]     = useState(false);
  const [selAssessment,  setSelAssessment]  = useState("");
  const [uanNumber,      setUanNumber]      = useState(user.profile?.uan_number      ?? "");
  const [aadharName,     setAadharName]     = useState(user.profile?.name_as_per_aadhar ?? "");
  const [panNumber,      setPanNumber]      = useState(user.profile?.pan_number      ?? "");

  // Fetch assessments when assessment step becomes visible
  useEffect(() => {
    if (!showAssessment || assessments.length > 0) return;
    setLoadAssess(true);
    clientApi
      .get<{ data: unknown }>(API.assessments.list, { params: { page_size: 100 } })
      .then(r => {
        const raw = r.data?.data;
        const list: AssessmentOption[] = Array.isArray(raw)
          ? (raw as AssessmentOption[])
          : ((raw as { results?: AssessmentOption[] })?.results ?? []);
        setAssessments(list);
      })
      .catch(() => setAssessments([]))
      .finally(() => setLoadAssess(false));
  }, [showAssessment, assessments.length]);

  function handleApproveClick() {
    setShowAssign(true);
    setAssignErr("");
  }

  // Returns null when valid, else the message to show — kept separate from
  // the dept/desig check so callers can decide whether a given failure
  // should also collapse the assessment step (dept/desig do; UAN/PAN don't,
  // matching this function's pre-existing behavior for UAN).
  function fieldValidationError(): string | null {
    if (uanNumber && uanNumber.length !== 12) {
      return "UAN must be exactly 12 digits, or leave it blank.";
    }
    if (panNumber && !PAN_RE.test(panNumber)) {
      return "Enter a valid PAN (e.g. ABCDE1234F), or leave it blank.";
    }
    return null;
  }

  function handleConfirm() {
    if (!selPosition) {
      setAssignErr("Select a Position before confirming.");
      return;
    }
    const fieldErr = fieldValidationError();
    if (fieldErr) {
      setAssignErr(fieldErr);
      return;
    }
    setAssignErr("");
    if (user.candidate_id) {
      setShowAssessment(true);
      return;
    }
    onAction(user.id, "approve", {
      position: selPosition,
      uanNumber: uanNumber || undefined, aadharName: aadharName || undefined,
      panNumber: panNumber ? panNumber.toUpperCase() : undefined,
    });
  }

  function handleAssessmentConfirm() {
    // The Position/UAN/PAN inputs stay visible (and editable) after the
    // Confirm click that advances to this step, so re-check here too —
    // without this, clearing the position after passing that first check
    // would silently submit a bad value and the backend would reject it.
    if (!selPosition) {
      setAssignErr("Select a Position before confirming.");
      setShowAssessment(false);
      return;
    }
    const fieldErr = fieldValidationError();
    if (fieldErr) {
      setAssignErr(fieldErr);
      return;
    }
    onAction(user.id, "approve", {
      position:     selPosition,
      assessmentId: selAssessment || undefined,
      uanNumber:    uanNumber    || undefined,
      aadharName:   aadharName   || undefined,
      panNumber:    panNumber ? panNumber.toUpperCase() : undefined,
    });
  }

  return (
    <>
    {previewDoc && previewDoc.file_url && (
      <DocPreviewModal
        name={previewDoc.document_type_display}
        fileName={previewDoc.file_name}
        fileUrl={previewDoc.file_url}
        fileSize={previewDoc.file_size}
        onClose={() => setPreviewDoc(null)}
      />
    )}
    <Modal
      title={`Review — ${user.full_name}`}
      onClose={onClose}
      maxWidth={560}
      footer={
        <>
          <button
            className="btn btn-ghost"
            style={{ color: "var(--error)", borderColor: "var(--error)" }}
            onClick={() => onAction(user.id, "reject")}
            disabled={acting}
          >
            {acting ? "…" : "Send Back for Corrections"}
          </button>

          {showAssessment ? (
            <button className="btn btn-filled" onClick={handleAssessmentConfirm} disabled={acting || loadAssess}>
              {acting
                ? <><i className="ti ti-loader-2 spin" /> Activating…</>
                : <><i className="ti ti-check" /> Confirm & Activate</>
              }
            </button>
          ) : showAssign ? (
            <button className="btn btn-filled" onClick={handleConfirm} disabled={acting}>
              {acting
                ? <><i className="ti ti-loader-2 spin" /> Activating…</>
                : user.candidate_id
                  ? <><i className="ti ti-arrow-right" /> Continue</>
                  : <><i className="ti ti-check" /> Confirm & Activate</>
              }
            </button>
          ) : (
            <button className="btn btn-filled" onClick={handleApproveClick} disabled={acting}>
              Approve & Activate ✓
            </button>
          )}
        </>
      }
    >
          {actionErr && <div className="alert alert-error" style={{ marginBottom: "1rem" }}>{actionErr}</div>}

          <Section title="Basic Info">
            <Row label="Email"       value={user.email} />
            <Row label="Phone"       value={user.phone} />
            <Row label="Department"  value={user.department} />
            <Row label="Designation" value={user.designation} />
            <Row label="Branch"      value={user.branch} />
            <Row label="Role"        value={user.role_display || "Candidate"} />
          </Section>

          {user.profile && (
            <>
              <Section title="Personal">
                <Row label="DOB"             value={user.profile.date_of_birth} />
                <Row label="Gender"          value={user.profile.gender} />
                <Row label="Marital Status"  value={user.profile.marital_status} />
                <Row label="Father Name"     value={user.profile.father_name} />
                <Row label="Blood Group"     value={user.profile.blood_group} />
                <Row label="Current Address" value={user.profile.current_address} />
              </Section>
              <Section title="Education & Experience">
                <Row label="Qualification"    value={user.profile.highest_qualification} />
                <Row label="Institution"      value={user.profile.institution} />
                <Row label="Year of Passing"  value={user.profile.year_of_passing?.toString()} />
                <Row label="Experience (yrs)" value={user.profile.total_experience_years} />
                <Row label="Prev Employer"    value={user.profile.previous_employer} />
              </Section>
              <Section title="Bank Details">
                <Row label="Account Holder" value={user.profile.account_holder_name} />
                <Row label="Account No."    value={user.profile.account_number ? `••••${user.profile.account_number.slice(-4)}` : undefined} />
                <Row label="IFSC"           value={user.profile.ifsc_code} />
                <Row label="Bank"           value={user.profile.bank_name} />
                <Row label="Branch"         value={user.profile.bank_branch_name} />
                <Row label="Account Type"   value={user.profile.account_type} />
              </Section>
              <Section title="Emergency Contact">
                <Row label="Name"         value={user.profile.emergency_name} />
                <Row label="Relationship" value={user.profile.emergency_relationship} />
                <Row label="Phone"        value={user.profile.emergency_phone} />
              </Section>
            </>
          )}

          <Section title={`Documents (${user.documents.length})`}>
            {user.documents.length === 0
              ? <p style={{ color: "var(--on-variant)", fontSize: ".85rem" }}>No documents uploaded.</p>
              : user.documents.map(d => (
                <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: ".4rem 0", borderBottom: "1px solid var(--outline-v)", fontSize: ".85rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                    <i className="ti ti-file-text" style={{ color: "var(--primary)", fontSize: 16, flexShrink: 0 }} />
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{d.document_type_display}</div>
                      <div style={{ color: "var(--on-variant)", fontSize: ".78rem", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: 200 }}>{d.file_name}</div>
                    </div>
                  </div>
                  {d.file_url
                    ? <button
                        className="btn btn-ghost btn-sm"
                        style={{ flexShrink: 0 }}
                        onClick={() => setPreviewDoc(d)}
                        title="Preview"
                      >
                        <i className="ti ti-eye" style={{ fontSize: 15 }} />
                      </button>
                    : <span style={{ fontSize: ".78rem", color: "var(--outline)" }}>No link</span>
                  }
                </div>
              ))
            }
          </Section>

          <div className="field-group" style={{ marginTop: "1rem" }}>
            <label className="field-label">Remarks (optional)</label>
            <textarea
              className="field-input"
              rows={3}
              value={remarks}
              onChange={e => onRemarksChange(e.target.value)}
              placeholder="Notes for the employee or for record…"
            />
          </div>

          {/* Assign dept/designation — revealed on approve click */}
          {showAssign && (
            <div style={{ marginTop: "1.25rem", padding: "1rem", borderRadius: 8, border: "1px solid var(--outline-v)", background: "var(--bg-mid)" }}>
              <div style={{ fontWeight: 700, fontSize: ".82rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--primary)", marginBottom: ".75rem" }}>
                <i className="ti ti-user-check" style={{ marginRight: 6 }} />Assign Role
              </div>

              {assignErr && (
                <div className="alert alert-error" style={{ marginBottom: ".75rem", padding: "6px 10px", fontSize: ".82rem" }}>
                  <i className="ti ti-alert-circle" /><span>{assignErr}</span>
                </div>
              )}

              <div className="field-group" style={{ marginBottom: ".75rem" }}>
                <label className="field-label">Org Unit <span style={{ color: "var(--error)" }}>*</span></label>
                <select
                  className="field-input field-select"
                  value={orgUnitId}
                  disabled={positionsLoading}
                  onChange={e => { setOrgUnitId(e.target.value); setSelPosition(""); setAssignErr(""); }}
                >
                  <option value="">— Select an org unit —</option>
                  {units.filter(u => u.is_active).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              </div>

              <div className="field-group" style={{ marginBottom: ".75rem" }}>
                <label className="field-label">Position <span style={{ color: "var(--error)" }}>*</span></label>
                <select
                  className="field-input field-select"
                  value={selPosition}
                  disabled={!orgUnitId}
                  onChange={e => { setSelPosition(e.target.value); setAssignErr(""); }}
                >
                  <option value="">
                    {!orgUnitId ? "Select an org unit first" : positionOptions.length === 0 ? "No vacant positions in this unit" : "— Select Position —"}
                  </option>
                  {positionOptions.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
                </select>
              </div>

              {selPosition && (
                <>
                  <div className="field-group" style={{ marginBottom: ".75rem" }}>
                    <label className="field-label">Department</label>
                    <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
                      {derivedDepartmentName || "(no department-level unit in this org unit's chain)"}
                    </div>
                  </div>

                  <div className="field-group">
                    <label className="field-label">Designation</label>
                    <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
                      {selectedPosition?.job_template_name || selectedPosition?.title}
                    </div>
                  </div>
                </>
              )}

              <div style={{ marginTop: ".75rem", padding: ".75rem", borderRadius: 6, background: "var(--bg)", border: "1px solid var(--outline-v)" }}>
                <div style={{ fontSize: ".78rem", fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".04em", marginBottom: ".5rem" }}>
                  EPF Details <span style={{ fontWeight: 400, textTransform: "none", fontSize: ".75rem" }}>(optional — can be filled later from employee profile)</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: ".5rem" }}>
                  <div className="field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label">UAN Number</label>
                    <input
                      className="field-input"
                      maxLength={12}
                      value={uanNumber}
                      onChange={e => setUanNumber(e.target.value.replace(/\D/g, ""))}
                      placeholder="12-digit UAN"
                    />
                    {uanNumber.length > 0 && uanNumber.length !== 12 && (
                      <div style={{ fontSize: ".72rem", color: "var(--warn)", marginTop: 3 }}>
                        {uanNumber.length}/12 digits
                      </div>
                    )}
                  </div>
                  <div className="field-group" style={{ marginBottom: 0 }}>
                    <label className="field-label">Name as per Aadhar</label>
                    <input
                      className="field-input"
                      value={aadharName}
                      onChange={e => setAadharName(e.target.value)}
                      placeholder="Exactly as on Aadhar card"
                    />
                  </div>
                  <div className="field-group" style={{ marginBottom: 0, gridColumn: "1 / -1" }}>
                    <label className="field-label">PAN Number</label>
                    <input
                      className="field-input"
                      maxLength={10}
                      value={panNumber}
                      onChange={e => setPanNumber(e.target.value.toUpperCase())}
                      placeholder="e.g. ABCDE1234F"
                    />
                    {panNumber.length > 0 && !PAN_RE.test(panNumber) && (
                      <div style={{ fontSize: ".72rem", color: "var(--warn)", marginTop: 3 }}>
                        5 letters, 4 digits, 1 letter — e.g. ABCDE1234F
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
          {/* Step 3 — Assign assessment (only for candidates from recruitment pipeline) */}
          {showAssessment && (
            <div style={{ marginTop: "1.25rem", padding: "1rem", borderRadius: 8, border: "1px solid var(--outline-v)", background: "var(--bg-mid)" }}>
              <div style={{ fontWeight: 700, fontSize: ".82rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--primary)", marginBottom: ".5rem" }}>
                <i className="ti ti-clipboard-list" style={{ marginRight: 6 }} />Assign Assessment
              </div>
              <p style={{ fontSize: ".82rem", color: "var(--on-variant)", marginBottom: ".75rem", lineHeight: 1.5 }}>
                This candidate came from the recruitment pipeline. You can assign an assessment for their onboarding period, or leave blank to skip.
              </p>
              <div className="field-group">
                <label className="field-label">Assessment <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>(optional)</span></label>
                {loadAssess ? (
                  <div style={{ fontSize: ".85rem", color: "var(--on-variant)" }}><i className="ti ti-loader-2 spin" /> Loading…</div>
                ) : (
                  <select
                    className="field-input field-select"
                    value={selAssessment}
                    onChange={e => setSelAssessment(e.target.value)}
                  >
                    <option value="">— No assessment —</option>
                    {assessments.map(a => <option key={a.id} value={a.id}>{a.title}</option>)}
                  </select>
                )}
              </div>
            </div>
          )}
    </Modal>
    </>
  );
}
