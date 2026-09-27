"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { FieldOption } from "../../_data";
import { formatDate } from "@/lib/formatDate";
import SearchableSelect from "@/components/SearchableSelect";

interface Props {
  employeeId: string;
  employeeName: string;
  currentDesignation: string;
  currentRole: string;
  // The Position/Org Unit this employee already holds (from their current
  // Placement) — prefills the Reassign Position modal below instead of
  // always starting blank, since this action is only ever taken on an
  // employee who already has both. Empty string when neither is known
  // (e.g. a Company Code Admin, who has no Position at all).
  currentPositionId: string;
  currentOrgUnitId: string;
  roleOptions: FieldOption[];
  // Position reassignment can change designation, department, and
  // (optionally, in the same action) role — a single callback covers all
  // three, unlike the old separate Promote Employee / Reassign Position
  // split this replaces.
  onPositionReassigned: (designation: string, department: string, role: string, positionId: string, orgUnitId: string) => void;
}

interface PromotionRecord {
  id: string;
  fromDesignation: string;
  toDesignation: string;
  roleChanged: boolean;
  effectiveDate: string;
  updatedBy: string;
  // The CTC (if any) tagged on the Salary tab as being "for" this specific
  // promotion — see EmployeeSalaryConfig.linked_promotion.
  linkedCtc: string | null;
}

// Shape returned by GET /employees/{id}/promotions/ (backend PromotionRecord model, snake_case).
interface ApiPromotionRecord {
  id: string;
  previous_designation: string;
  new_designation: string;
  role_changed: boolean;
  effective_date: string;
  promoted_by: string;
  linked_ctc: string | null;
}

const toPromotionRecord = (r: ApiPromotionRecord): PromotionRecord => ({
  id: r.id,
  fromDesignation: r.previous_designation || "—",
  toDesignation: r.new_designation || "—",
  roleChanged: r.role_changed,
  effectiveDate: r.effective_date,
  updatedBy: r.promoted_by || "—",
  linkedCtc: r.linked_ctc,
});

const INR = (n: string | number) =>
  `₹${Number(n).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

const fmtDate = (d: string) => formatDate(d);

const labelFor = (options: FieldOption[], value: string) =>
  options.find(o => o.value === value)?.label ?? value;

export default function PromotionTab({
  employeeId, employeeName, currentDesignation, currentRole,
  currentPositionId, currentOrgUnitId, roleOptions, onPositionReassigned,
}: Props) {
  const canEdit = usePermission("employees.edit");

  const [history, setHistory] = useState<PromotionRecord[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [showReassignModal, setShowReassignModal] = useState(false);
  const [reassignOrgUnit, setReassignOrgUnit] = useState("");
  const [reassignPosition, setReassignPosition] = useState("");
  const [reassignDate, setReassignDate] = useState("");
  const [reassignRole, setReassignRole] = useState(currentRole);
  const [roleConfirmed, setRoleConfirmed] = useState(false);
  const [reassignSubmitting, setReassignSubmitting] = useState(false);
  const [reassignError, setReassignError] = useState<string | null>(null);
  const { units, positionsForUnit, loading: positionsLoading } = useOrgUnitsAndPositions();
  const reassignPositionOptions = positionsForUnit(reassignOrgUnit);
  const reassignSelectedPosition = reassignPositionOptions.find(p => p.id === reassignPosition);
  const isElevated = reassignRole !== currentRole;
  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside the modal and releasing past its edge would otherwise land on the
  // overlay and close it. Only close when the gesture both started AND ended
  // on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const res = await clientApi.get(API.employees.promotions(employeeId));
      const records = (res.data?.data ?? []) as ApiPromotionRecord[];
      setHistory(records.map(toPromotionRecord));
    } catch {
      // History is supplementary to the rest of this tab — a failed fetch
      // just leaves the table empty rather than blocking the page.
    } finally {
      setHistoryLoading(false);
    }
  }, [employeeId]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  function openReassignModal() {
    // Prefilled to what the employee already holds — HR is reassigning an
    // existing employee here (not hiring fresh), so starting blank meant
    // reconstructing their current Org Unit/Position from scratch every
    // time even when only the Role, or just the Position within the same
    // Org Unit, is actually changing.
    setReassignOrgUnit(currentOrgUnitId);
    setReassignPosition(currentPositionId);
    setReassignDate(new Date().toISOString().split("T")[0]);
    setReassignRole(currentRole);
    setRoleConfirmed(false);
    setReassignError(null);
    setShowReassignModal(true);
  }

  async function submitReassign() {
    if (!reassignPosition) {
      setReassignError("Select a position.");
      return;
    }
    if (!reassignDate) {
      setReassignError("Effective date is required.");
      return;
    }
    if (isElevated && !roleConfirmed) {
      setReassignError("Confirm the role change before submitting.");
      return;
    }
    setReassignSubmitting(true);
    setReassignError(null);
    try {
      const res = await clientApi.put(API.employees.detail(employeeId), {
        position: reassignPosition, effective_date: reassignDate,
        ...(isElevated ? { role: reassignRole } : {}),
      });
      const updated = res.data?.data as {
        designation?: string; department?: string; role?: string;
        position_id?: string | null; org_unit_id?: string | null;
      } | undefined;
      await fetchHistory();
      onPositionReassigned(
        updated?.designation ?? currentDesignation,
        updated?.department ?? "",
        updated?.role ?? currentRole,
        updated?.position_id ?? reassignPosition,
        updated?.org_unit_id ?? reassignOrgUnit,
      );
      setShowReassignModal(false);
      setSuccessMsg(
        isElevated
          ? "Position and role reassigned. New access applies at the employee's next login."
          : "Position reassigned. Designation and department updated to match."
      );
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to reassign position. Please try again.";
      setReassignError(msg);
    } finally {
      setReassignSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {successMsg && (
        <div className="alert alert-success"><i className="ti ti-circle-check" />{successMsg}</div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Current Designation</span>
          {canEdit && (
            <button className="btn btn-filled btn-sm" onClick={openReassignModal}>
              <i className="ti ti-sitemap" /> Reassign Position
            </button>
          )}
        </div>
        <div className="card-body">
          <div className="text-[20px] font-semibold">{currentDesignation || "—"}</div>
          <div className="text-[13px] text-muted mt-1">
            {employeeName} · {labelFor(roleOptions, currentRole)}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Promotion History</span>
        </div>
        {historyLoading ? (
          <div className="empty-state">
            <i className="ti ti-loader-2 spin" />
            <h3>Loading history…</h3>
          </div>
        ) : history.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-award" />
            <h3>No promotions yet</h3>
            <p>Designation and role changes for this employee will be listed here.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Change</th>
                  <th>Effective date</th>
                  <th>Updated by</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id}>
                    <td>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span>{h.fromDesignation}</span>
                        <i className="ti ti-arrow-right text-muted" />
                        <span className="font-medium">{h.toDesignation}</span>
                        {h.roleChanged && <span className="badge badge-warn">Role change</span>}
                        {h.linkedCtc && (
                          <span className="badge badge-success" title="CTC revised for this promotion — see the Salary tab">
                            <i className="ti ti-currency-rupee" /> {INR(h.linkedCtc)}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="tabular-nums">{fmtDate(h.effectiveDate)}</td>
                    <td>{h.updatedBy}</td>
                    <td><span className="badge badge-success">Applied</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showReassignModal && (
        <div
          className="modal-overlay open"
          onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
          onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) setShowReassignModal(false); }}
        >
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Reassign Position</span>
              <button className="modal-close" onClick={() => setShowReassignModal(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body flex flex-col gap-4">
              {reassignError && <div className="alert alert-error">{reassignError}</div>}

              <div className="field-group">
                <label className="field-label">Org Unit</label>
                <SearchableSelect
                  inputClassName="field-input"
                  value={reassignOrgUnit}
                  disabled={positionsLoading}
                  onChange={v => { setReassignOrgUnit(v); setReassignPosition(""); setReassignError(null); }}
                  placeholder="— Select an org unit —"
                  options={units.filter(u => u.is_active).map(u => ({ value: u.id, label: u.name }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Position</label>
                <SearchableSelect
                  inputClassName="field-input"
                  value={reassignPosition}
                  disabled={!reassignOrgUnit}
                  onChange={v => { setReassignPosition(v); setReassignError(null); }}
                  placeholder={!reassignOrgUnit ? "Select an org unit first" : reassignPositionOptions.length === 0 ? "No active positions in this unit" : "— Select Position —"}
                  options={reassignPositionOptions.map(p => ({
                    value: p.id,
                    label: `${p.title}${p.holder_name ? ` — currently ${p.holder_name}` : " (vacant)"}`,
                  }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Effective date</label>
                <input
                  className="field-input"
                  type="date"
                  value={reassignDate}
                  onChange={e => { setReassignDate(e.target.value); setReassignError(null); }}
                />
              </div>

              <div className="field-group">
                <label className="field-label">New role <span className="text-muted">(optional)</span></label>
                <SearchableSelect
                  inputClassName="field-input"
                  value={reassignRole}
                  onChange={v => { setReassignRole(v); setRoleConfirmed(false); setReassignError(null); }}
                  options={[
                    ...(!roleOptions.find(o => o.value === currentRole) ? [{ value: currentRole, label: currentRole }] : []),
                    ...roleOptions,
                  ]}
                />
              </div>

              {reassignSelectedPosition?.holder_name && reassignSelectedPosition.holder_employee_id !== employeeId && (
                <div className="alert alert-warn">
                  <i className="ti ti-info-circle" />
                  {reassignSelectedPosition.holder_name}&apos;s placement on this position will be closed the day
                  before the effective date above and kept in history.
                </div>
              )}

              {isElevated && (
                <>
                  <div className="alert alert-warn">
                    <i className="ti ti-shield-lock" />
                    This grants {labelFor(roleOptions, reassignRole)} access. New permissions apply at the
                    employee&apos;s next login.
                  </div>
                  <label className="flex items-start gap-2 text-[13px]">
                    <input
                      type="checkbox"
                      className="mt-0.5"
                      checked={roleConfirmed}
                      onChange={e => setRoleConfirmed(e.target.checked)}
                    />
                    I confirm this role change and its access impact.
                  </label>
                </>
              )}

              <div className="text-[11.5px] text-muted">
                Designation (and department, if this org unit is linked to one) will update to match the new
                position. A future-dated effective date schedules the change without affecting today&apos;s values.
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowReassignModal(false)} disabled={reassignSubmitting}>
                Cancel
              </button>
              <button className="btn btn-filled" onClick={submitReassign} disabled={reassignSubmitting || !reassignPosition}>
                {reassignSubmitting ? <><i className="ti ti-loader-2 spin" /> Reassigning…</> : "Reassign"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
