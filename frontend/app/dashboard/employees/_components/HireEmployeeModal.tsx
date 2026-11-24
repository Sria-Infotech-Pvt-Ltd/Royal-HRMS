"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import SearchableSelect from "@/components/SearchableSelect";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import { usePermission } from "@/hooks/usePermission";
import type { Position } from "@/types/orgStructure";
import HireWizardClient from "@/app/dashboard/hire/[hireActionId]/_components/HireWizardClient";
import DateInput from "@/components/shared/DateInput";
import FieldError from "@/components/shared/FieldError";

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

const MIN_JOINING_DATE = "1990-01-01"; // earliest date a hire can be back-dated to (same limit as the backend)

export default function HireEmployeeModal({ onClose, onHired, initialHireActionId }: {
  onClose: () => void; onHired?: () => void; initialHireActionId?: string;
}) {
  const t = useT();
  const { units, positionsForUnit, resolveDepartmentName, loading: positionsLoading } = useOrgUnitsAndPositions();
  const canCreatePosition = usePermission("org_structure.create");

  const todayStr = new Date().toISOString().slice(0, 10);
  const [hireActionId, setHireActionId] = useState<string | null>(initialHireActionId ?? null);
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(todayStr);
  const [orgUnitId, setOrgUnitId] = useState("");
  const [positionId, setPositionId] = useState("");
  const [err, setErr] = useState("");
  // One message per field, all shown at once; each clears as soon as its own field is corrected.
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<"reason" | "effectiveFrom" | "orgUnit" | "position", string>>>({});
  function clearFieldError(field: keyof typeof fieldErrors) {
    setFieldErrors(previous => ({ ...previous, [field]: undefined }));
    setErr("");
  }
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
    if (!newPosTitle.trim()) { setCreatePosErr(t("Position title is required.")); return; }
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
      setCreatePosErr((e as { message?: string })?.message || t("Could not create the position. Please try again."));
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
    const found: typeof fieldErrors = {};
    if (!reason) found.reason = t("Select a reason.");
    if (!effectiveFrom) found.effectiveFrom = t("Effective from is required.");
    else if (effectiveFrom < MIN_JOINING_DATE) found.effectiveFrom = t("Effective from cannot be before 01-01-1990."); // past dates are allowed for back-dated hires
    if (!orgUnitId) found.orgUnit = t("Select an org unit.");
    if (!positionId) found.position = t("Select a position.");
    setFieldErrors(found);
    const firstInvalid = (["reason", "effectiveFrom", "orgUnit", "position"] as const).find(field => found[field]);
    if (firstInvalid) {
      // Take the person to the first problem instead of leaving it off-screen.
      document.getElementById(`hire-field-${firstInvalid}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    setSaving(true);
    setErr("");
    try {
      const { data } = await clientApi.post<{ data: { id: string } }>(API.hireActions.list, {
        reason, effective_from: effectiveFrom, position: positionId,
      });
      setHireActionId(data.data.id);
    } catch (e) {
      setErr((e as { message?: string })?.message || t("Something went wrong. Please try again."));
      setSaving(false);
    }
  }

  return (
    <Modal
      title={<h2 className="modal-title">{t("Hire an")} <em style={{ color: "var(--brand-ink)" }}>{t("employee")}</em></h2>}
      onClose={onClose}
      // Without this, the whole modal (body + footer) scrolled as one
      // block — on a short viewport (QA report #28: 643px) the
      // Continue/Cancel footer buttons ended up below the fold with no
      // sticky footer to keep them reachable without scrolling.
      scrollBody
      footer={
        <>
          <button onClick={onClose} disabled={saving} className="btn btn-ghost">{t("Cancel")}</button>
          <button onClick={submit} disabled={saving} className="btn btn-filled">
            {saving ? t("Continuing…") : t("Continue to hiring form →")}
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
          {t("Start a Hire action. HR completes the hiring form here, so this employee will go directly to their dashboard after their first password change rather than receiving the self-service onboarding wizard.")}
        </p>

        <div className="section-label">{t("Action")}</div>
        <div className="g3">
          <div className="f">
            <label>{t("Action type")}</label>
            {/* .finput's height/padding assume a real <input>/<select>,
                which the browser vertically centers natively — a plain
                <div> doesn't get that for free, so "Hire" sat at the top
                of the box instead of centered like every sibling field. */}
            <div className="finput" style={{ cursor: "not-allowed", display: "flex", alignItems: "center" }}>{t("Hire")}</div>
          </div>
          <div className="f">
            <label id="hire-field-reason">{t("Reason")} <span className="req">*</span></label>
            <SearchableSelect value={reason} onChange={value => { setReason(value); clearFieldError("reason"); }} placeholder={t("Select a reason")} options={REASONS.map(reasonOption => ({ value: reasonOption.value, label: t(reasonOption.label) }))} />
            <FieldError message={fieldErrors.reason} />
          </div>
          <div className="f">
            <label id="hire-field-effectiveFrom">{t("Effective from")} <span className="req">*</span></label>
            <DateInput min={MIN_JOINING_DATE} value={effectiveFrom} onChange={value => { setEffectiveFrom(value); clearFieldError("effectiveFrom"); }} className="finput" separator="-" />
            <FieldError message={fieldErrors.effectiveFrom} />
            <p className="hint">{t("This becomes the date of joining.")}</p>
          </div>
        </div>

        <div className="section-label">{t("Fields this hire may change")}</div>
        <div className="g2">
          <div className="f">
            {/* Position (required) can't be picked until an org unit is
                selected — QA report #30 found only Position marked
                required, leaving no visual cue for why it stayed
                unselectable. */}
            <label id="hire-field-orgUnit">{t("Org unit")} <span className="req">*</span></label>
            <SearchableSelect
              value={orgUnitId}
              onChange={v => { setOrgUnitId(v); setPositionId(""); clearFieldError("orgUnit"); }}
              disabled={positionsLoading}
              placeholder={t("Select an org unit")}
              options={units.filter(u => u.is_active).map(u => ({ value: u.id, label: u.name }))}
            />
            <FieldError message={fieldErrors.orgUnit} />
          </div>
          <div className="f">
            <label id="hire-field-position">{t("Position")} <span className="req">*</span></label>
            <SearchableSelect
              value={positionId}
              onChange={value => { setPositionId(value); clearFieldError("position"); }}
              disabled={!orgUnitId || positionsLoading}
              placeholder={!orgUnitId ? t("Select an org unit first") : t("Select a position")}
              options={positionOptions.map(p => ({ value: p.id, label: p.title }))}
            />
            <FieldError message={fieldErrors.position} />
            {orgUnitId && !positionsLoading && canCreatePosition && !showCreatePosition && (
              <button
                type="button"
                onClick={openCreatePosition}
                className="hint"
                style={{ background: "none", border: "none", padding: 0, marginTop: 4, cursor: "pointer", color: "var(--brand-ink)", textAlign: "left" }}
              >
                <i className="ti ti-plus" style={{ fontSize: 11, marginRight: 3 }} />
                {positionOptions.length === 0 ? t("No vacant position here — create one") : t("Create a new position")}
              </button>
            )}
          </div>
        </div>
        {selectedPosition && (
          <p className="hint">
            {t("Org unit →")} {selectedPosition.title} · {departmentName ?? units.find(u => u.id === orgUnitId)?.name}
            {selectedPosition.grade ? ` · ${t("Band {grade}", { grade: selectedPosition.grade })}` : ""}
          </p>
        )}

        {showCreatePosition && (
          <div className="rounded-lg p-3.5 space-y-3" style={{ background: "var(--sunken)" }}>
            <div className="section-label" style={{ margin: 0 }}>
              {t("New position in {unit}", { unit: units.find(u => u.id === orgUnitId)?.name ?? "" })}
            </div>
            {createPosErr && (
              <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
                <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
                <span className="text-[13px]">{createPosErr}</span>
              </div>
            )}
            <div className="g2">
              <div className="f">
                <label>{t("Position title")} <span className="req">*</span></label>
                <input type="text" value={newPosTitle} onChange={e => setNewPosTitle(e.target.value)}
                  placeholder={t("e.g. Senior Executive")} className="finput" />
              </div>
              <div className="f">
                <label>{t("Grade / band")}</label>
                <input type="text" value={newPosGrade} onChange={e => setNewPosGrade(e.target.value)}
                  placeholder={t("Optional")} className="finput" />
              </div>
            </div>
            <div className="flex gap-2 justify-end">
              <button type="button" onClick={() => setShowCreatePosition(false)} disabled={creatingPosition} className="btn btn-ghost">
                {t("Cancel")}
              </button>
              <button type="button" onClick={createPosition} disabled={creatingPosition} className="btn btn-filled">
                {creatingPosition ? t("Creating…") : t("Create position")}
              </button>
            </div>
          </div>
        )}

        <div className="section-label">{t("Employee details — not changed by this action")}</div>
        <div className="rounded-lg p-3.5 space-y-1.5" style={{ background: "var(--sunken)" }}>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>{t("Employee")}</span>
            <span className="font-semibold">{t("Not yet created — captured in the hiring form")}</span>
          </div>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>{t("First record")}</span>
            <span className="font-semibold">{t("{date} → 31-12-9999", { date: effectiveFrom ? formatDate(effectiveFrom) : "—" })}</span>
          </div>
          <div className="flex justify-between text-[12.5px]">
            <span style={{ color: "var(--muted)" }}>{t("Employee number")}</span>
            <span className="font-semibold">{t("Reserved from the series for the employment type")}</span>
          </div>
        </div>
        <p className="hint">
          {t("Creates the first record, valid {date} → 31-12-9999.", { date: effectiveFrom ? formatDate(effectiveFrom) : "—" })}
        </p>
      </div>
    </Modal>
  );
}
