"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import SearchableSelect from "@/components/SearchableSelect";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import { usePermission } from "@/hooks/usePermission";
import type { Position } from "@/types/orgStructure";
import HireWizardClient from "@/app/dashboard/hire/[hireActionId]/_components/HireWizardClient";

// Stage 1 of the two-stage Hire flow — collects just enough to reserve a
// HireAction (reason/effective date/position) before any User exists. Once
// created, this same modal switches to rendering the wizard (Stage 2) for
// that HireAction — never a page navigation, so the Employee Directory
// stays visible/dimmed behind it the whole time, exactly like every other
// modal in this app.

const REASONS = [
  { value: "new_position",       label: "New position" },
  { value: "replacement",        label: "Replacement" },
  { value: "backfill",           label: "Backfill" },
  { value: "business_expansion", label: "Business expansion" },
  { value: "rehire",             label: "Rehire" },
];

export default function HireEmployeeModal({ onClose, onHired, initialHireActionId }: {
  onClose: () => void; onHired?: () => void; initialHireActionId?: string;
}) {
  const { units, positionsForUnit, resolveDepartmentName, loading: positionsLoading } = useOrgUnitsAndPositions();
  const canCreatePosition = usePermission("org_structure.create");

  const todayStr = new Date().toISOString().slice(0, 10);
  const [hireActionId, setHireActionId] = useState<string | null>(initialHireActionId ?? null);
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(todayStr);
  const [orgUnitId, setOrgUnitId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  // The shared org-unit/position hook has no way to add a just-created
  // Position to its list without a full refetch — kept here as a small
  // local overlay instead, merged into positionOptions below, so a newly
  // created position shows up (and gets auto-selected) immediately without
  // waiting on/forcing a refetch of every org unit's positions.
  const [extraPositions, setExtraPositions] = useState<Position[]>([]);
  const [showCreatePosition, setShowCreatePosition] = useState(false);
  const [newPosTitle, setNewPosTitle] = useState("");
  const [newPosGrade, setNewPosGrade] = useState("");
  const [creatingPosition, setCreatingPosition] = useState(false);
  const [createPosErr, setCreatePosErr] = useState("");

  const positionOptions = [
    ...positionsForUnit(orgUnitId, /* vacantOnly */ true),
    ...extraPositions.filter(p => p.org_unit === orgUnitId),
  ];
  const selectedPosition = positionOptions.find(p => p.id === positionId);
  const departmentName = resolveDepartmentName(orgUnitId);

  function openCreatePosition() {
    setNewPosTitle(""); setNewPosGrade(""); setCreatePosErr("");
    setShowCreatePosition(true);
  }

  async function createPosition() {
    if (!newPosTitle.trim()) { setCreatePosErr("Position title is required."); return; }
    setCreatingPosition(true);
    setCreatePosErr("");
    try {
      const { data } = await clientApi.post<{ data: Position }>(API.orgStructure.positions.list, {
        org_unit: orgUnitId, title: newPosTitle.trim(), grade: newPosGrade.trim(),
        is_chief: false, job_template: null,
      });
      setExtraPositions(prev => [...prev, data.data]);
      setPositionId(data.data.id);
      setShowCreatePosition(false);
    } catch (e) {
      setCreatePosErr((e as { message?: string })?.message || "Could not create the position. Please try again.");
    } finally {
      setCreatingPosition(false);
    }
  }

  if (hireActionId) {
    return (
      <HireWizardClient
        hireActionId={hireActionId}
        onClose={onClose}
        onHired={() => { onHired?.(); onClose(); }}
      />
    );
  }

  async function submit() {
    if (!reason)         { setErr("Select a reason.");        return; }
    if (!effectiveFrom)  { setErr("Effective from is required."); return; }
    if (effectiveFrom < todayStr) { setErr("Effective from cannot be in the past."); return; }
    if (!orgUnitId)      { setErr("Select an org unit.");     return; }
    if (!positionId)     { setErr("Select a position.");      return; }
    setSaving(true);
    setErr("");
    try {
      const { data } = await clientApi.post<{ data: { id: string } }>(API.hireActions.list, {
        reason, effective_from: effectiveFrom, position: positionId,
      });
      setHireActionId(data.data.id);
    } catch (e) {
      setErr((e as { message?: string })?.message || "Something went wrong. Please try again.");
      setSaving(false);
    }
  }

  return (
    <Modal
      title={<h2 className="modal-title">Hire an <em style={{ color: "var(--brand-ink)" }}>employee</em></h2>}
      onClose={onClose}
      // Without this, the whole modal (body + footer) scrolled as one
      // block — on a short viewport (QA report #28: 643px) the
      // Continue/Cancel footer buttons ended up below the fold with no
      // sticky footer to keep them reachable without scrolling.
      scrollBody
      footer={
        <>
          <button onClick={onClose} disabled={saving} className="btn btn-ghost">Cancel</button>
          <button onClick={submit} disabled={saving} className="btn btn-filled">
            {saving ? "Continuing…" : "Continue to hiring form →"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {err && (
          <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
            <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
            <span className="text-[13px]">{err}</span>
          </div>
        )}

        <p className="hint">
          Start a Hire action. The hiring form opens next, pre-filled with what you enter here.
        </p>

        <div className="section-label">Action</div>
        <div className="g3">
          <div className="f">
            <label>Action type</label>
            <div className="finput" style={{ cursor: "not-allowed" }}>Hire</div>
          </div>
          <div className="f">
            <label>Reason <span className="req">*</span></label>
            <SearchableSelect value={reason} onChange={setReason} placeholder="Select a reason" options={REASONS} />
          </div>
          <div className="f">
            <label>Effective from <span className="req">*</span></label>
            <input type="date" min={todayStr} value={effectiveFrom} onChange={e => setEffectiveFrom(e.target.value)} className="finput" />
            <p className="hint">This becomes the date of joining.</p>
          </div>
        </div>

        <div className="section-label">Fields this hire may change</div>
        <div className="g2">
          <div className="f">
            {/* Position (required) can't be picked until an org unit is
                selected — QA report #30 found only Position marked
                required, leaving no visual cue for why it stayed
                unselectable. */}
            <label>Org unit <span className="req">*</span></label>
            <SearchableSelect
              value={orgUnitId}
              onChange={v => { setOrgUnitId(v); setPositionId(""); }}
              disabled={positionsLoading}
              placeholder="Select an org unit"
              options={units.filter(u => u.is_active).map(u => ({ value: u.id, label: u.name }))}
            />
          </div>
          <div className="f">
            <label>Position <span className="req">*</span></label>
            <SearchableSelect
              value={positionId}
              onChange={setPositionId}
              disabled={!orgUnitId || positionsLoading}
              placeholder={!orgUnitId ? "Select an org unit first" : "Select a position"}
              options={positionOptions.map(p => ({ value: p.id, label: p.title }))}
            />
            {orgUnitId && !positionsLoading && canCreatePosition && !showCreatePosition && (
              <button
                type="button"
                onClick={openCreatePosition}
                className="hint"
                style={{ background: "none", border: "none", padding: 0, marginTop: 4, cursor: "pointer", color: "var(--brand-ink)", textAlign: "left" }}
              >
                <i className="ti ti-plus" style={{ fontSize: 11, marginRight: 3 }} />
                {positionOptions.length === 0 ? "No vacant position here — create one" : "Create a new position"}
              </button>
            )}
          </div>
        </div>
        {selectedPosition && (
          <p className="hint">
            Org unit → {selectedPosition.title} · {departmentName ?? units.find(u => u.id === orgUnitId)?.name}
            {selectedPosition.grade ? ` · Band ${selectedPosition.grade}` : ""}
          </p>
        )}

        {showCreatePosition && (
          <div className="rounded-lg p-3.5 space-y-3" style={{ background: "var(--sunken)" }}>
            <div className="section-label" style={{ margin: 0 }}>
              New position in {units.find(u => u.id === orgUnitId)?.name}
            </div>
            {createPosErr && (
              <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
                <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
                <span className="text-[13px]">{createPosErr}</span>
              </div>
            )}
            <div className="g2">
              <div className="f">
                <label>Position title <span className="req">*</span></label>
                <input type="text" value={newPosTitle} onChange={e => setNewPosTitle(e.target.value)}
                  placeholder="e.g. Senior Executive" className="finput" />
              </div>
              <div className="f">
                <label>Grade / band</label>
                <input type="text" value={newPosGrade} onChange={e => setNewPosGrade(e.target.value)}
                  placeholder="Optional" className="finput" />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreatePosition(false)} disabled={creatingPosition} className="btn btn-ghost">
                Cancel
              </button>
              <button type="button" onClick={createPosition} disabled={creatingPosition} className="btn btn-filled">
                {creatingPosition ? "Creating…" : "Create position"}
              </button>
            </div>
          </div>
        )}

        <div className="section-label">Employee details — not changed by this action</div>
        <div className="rounded-lg p-3.5 space-y-1.5" style={{ background: "var(--sunken)" }}>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>Employee</span>
            <span className="font-semibold">Not yet created — captured in the hiring form</span>
          </div>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>First record</span>
            <span className="font-semibold">{effectiveFrom ? formatDate(effectiveFrom) : "—"} → 31-12-9999</span>
          </div>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>Employee number</span>
            <span className="font-semibold">Reserved from the series for the employment type</span>
          </div>
        </div>
        <p className="hint">
          Creates the first record, valid {effectiveFrom ? formatDate(effectiveFrom) : "—"} → 31-12-9999.
        </p>
      </div>
    </Modal>
  );
}
