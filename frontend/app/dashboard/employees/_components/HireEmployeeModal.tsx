"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
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

  const todayStr = new Date().toISOString().slice(0, 10);
  const [hireActionId, setHireActionId] = useState<string | null>(initialHireActionId ?? null);
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(todayStr);
  const [orgUnitId, setOrgUnitId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);

  const positionOptions = positionsForUnit(orgUnitId, /* vacantOnly */ true);
  const selectedPosition = positionOptions.find(p => p.id === positionId);
  const departmentName = resolveDepartmentName(orgUnitId);

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
            <select value={reason} onChange={e => setReason(e.target.value)} className="finput" style={{ cursor: "pointer" }}>
              <option value="">Select a reason</option>
              {REASONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
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
            <label>Org unit</label>
            <select value={orgUnitId} onChange={e => { setOrgUnitId(e.target.value); setPositionId(""); }}
              disabled={positionsLoading} className="finput" style={{ cursor: "pointer" }}>
              <option value="">Select an org unit</option>
              {units.filter(u => u.is_active).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
          <div className="f">
            <label>Position <span className="req">*</span></label>
            <select value={positionId} onChange={e => setPositionId(e.target.value)}
              disabled={!orgUnitId || positionsLoading} className="finput" style={{ cursor: "pointer" }}>
              <option value="">{!orgUnitId ? "Select an org unit first" : "Select a position"}</option>
              {positionOptions.map(p => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select>
          </div>
        </div>
        {selectedPosition && (
          <p className="hint">
            Org unit → {selectedPosition.title} · {departmentName ?? units.find(u => u.id === orgUnitId)?.name}
            {selectedPosition.grade ? ` · Band ${selectedPosition.grade}` : ""}
          </p>
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
