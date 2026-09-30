"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { Asset, AssetAssignment, EmployeeAssetsResponse, AssetCondition } from "@/types/assets";
import { ASSET_CONDITION_OPTIONS } from "@/types/assets";

interface Props {
  employeeId: string;
}

interface PagedResponse<T> { results: T[] }

const fmtDate = (d: string) =>
  new Date(d).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const BLANK_ASSIGN = { asset: "", assigned_date: "", condition_at_assignment: "new" as AssetCondition, expected_return_date: "", remarks: "" };
const BLANK_RETURN = { return_date: "", return_condition: "good" as AssetCondition, return_reason: "", remarks: "" };

export default function AssetsTab({ employeeId }: Props) {
  const canEdit = usePermission("assets.edit");

  const [current, setCurrent] = useState<AssetAssignment[]>([]);
  const [history, setHistory] = useState<AssetAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const mouseDownOnOverlay = useRef(false);

  // ── Assign ──
  const [showAssign, setShowAssign] = useState(false);
  const [availableAssets, setAvailableAssets] = useState<Asset[]>([]);
  const [assignForm, setAssignForm] = useState(BLANK_ASSIGN);
  const [assignError, setAssignError] = useState<string | null>(null);
  const [assigning, setAssigning] = useState(false);

  // ── Return ──
  const [returnTarget, setReturnTarget] = useState<AssetAssignment | null>(null);
  const [returnForm, setReturnForm] = useState(BLANK_RETURN);
  const [returnError, setReturnError] = useState<string | null>(null);
  const [returning, setReturning] = useState(false);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await clientApi.get(API.assets.employeeAssets(employeeId));
      const data = (res.data?.data ?? { current: [], history: [] }) as EmployeeAssetsResponse;
      setCurrent(data.current);
      setHistory(data.history);
    } catch {
      // Supplementary to the rest of the profile — a failed fetch just
      // leaves the tables empty rather than blocking the page.
    } finally {
      setLoading(false);
    }
  }, [employeeId]);

  useEffect(() => { fetchAssets(); }, [fetchAssets]);

  async function openAssign() {
    setAssignForm({ ...BLANK_ASSIGN, assigned_date: new Date().toISOString().split("T")[0] });
    setAssignError(null);
    setShowAssign(true);
    try {
      const res = await clientApi.get(`${API.assets.list}?status=available&page_size=200`);
      const data = res.data?.data as PagedResponse<Asset> | undefined;
      setAvailableAssets(data?.results ?? []);
    } catch {
      setAvailableAssets([]);
    }
  }

  async function submitAssign() {
    if (!assignForm.asset) { setAssignError("Select an asset to assign."); return; }
    if (!assignForm.assigned_date) { setAssignError("Assigned date is required."); return; }
    setAssigning(true);
    setAssignError(null);
    try {
      await clientApi.post(API.assets.assign(employeeId), {
        asset: assignForm.asset,
        assigned_date: assignForm.assigned_date,
        condition_at_assignment: assignForm.condition_at_assignment,
        expected_return_date: assignForm.expected_return_date || null,
        remarks: assignForm.remarks,
      });
      setShowAssign(false);
      await fetchAssets();
      setSuccessMsg("Asset assigned successfully.");
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to assign asset.";
      setAssignError(msg);
    } finally {
      setAssigning(false);
    }
  }

  function openReturn(assignment: AssetAssignment) {
    setReturnForm({ ...BLANK_RETURN, return_date: new Date().toISOString().split("T")[0] });
    setReturnError(null);
    setReturnTarget(assignment);
  }

  async function submitReturn() {
    if (!returnTarget) return;
    if (!returnForm.return_date) { setReturnError("Return date is required."); return; }
    if (!returnForm.return_reason.trim()) { setReturnError("Return reason is required."); return; }
    setReturning(true);
    setReturnError(null);
    try {
      await clientApi.post(API.assets.return(returnTarget.id), returnForm);
      setReturnTarget(null);
      await fetchAssets();
      setSuccessMsg("Asset returned successfully.");
      setTimeout(() => setSuccessMsg(null), 5000);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to return asset.";
      setReturnError(msg);
    } finally {
      setReturning(false);
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {successMsg && (
        <div className="alert alert-success"><i className="ti ti-circle-check" />{successMsg}</div>
      )}

      <div className="card">
        <div className="card-header">
          <span className="card-title">Assigned Assets</span>
          {canEdit && (
            <button className="btn btn-filled btn-sm" onClick={openAssign}>
              <i className="ti ti-plus" /> Assign Asset
            </button>
          )}
        </div>
        {loading ? (
          <div className="empty-state">
            <i className="ti ti-loader-2 spin" />
            <h3>Loading assets…</h3>
          </div>
        ) : current.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-package" />
            <h3>No assets assigned</h3>
            <p>Company equipment assigned to this employee will be listed here.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asset Tag</th>
                  <th>Asset Name</th>
                  <th>Type</th>
                  <th>Serial Number</th>
                  <th>Assigned Date</th>
                  <th>Condition</th>
                  <th>Status</th>
                  {canEdit && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {current.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{a.asset_tag}</td>
                    <td>{a.asset_name}</td>
                    <td>{a.asset_type}</td>
                    <td>{a.serial_number || "—"}</td>
                    <td className="tabular-nums">{fmtDate(a.assigned_date)}</td>
                    <td>{a.condition_at_assignment}</td>
                    <td><span className="badge badge-info">{a.status_display}</span></td>
                    {canEdit && (
                      <td>
                        <button className="btn btn-ghost btn-sm" onClick={() => openReturn(a)}>
                          <i className="ti ti-corner-down-left" /> Return
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <span className="card-title">Asset History</span>
        </div>
        {!loading && history.length === 0 ? (
          <div className="empty-state">
            <i className="ti ti-history" />
            <h3>No returned assets yet</h3>
          </div>
        ) : !loading && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Asset Tag</th>
                  <th>Asset Name</th>
                  <th>Assigned</th>
                  <th>Returned</th>
                  <th>Return Condition</th>
                  <th>Return Reason</th>
                </tr>
              </thead>
              <tbody>
                {history.map(a => (
                  <tr key={a.id}>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{a.asset_tag}</td>
                    <td>{a.asset_name}</td>
                    <td className="tabular-nums">{fmtDate(a.assigned_date)}</td>
                    <td className="tabular-nums">{a.return_date ? fmtDate(a.return_date) : "—"}</td>
                    <td>{a.return_condition || "—"}</td>
                    <td>{a.return_reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Assign modal ── */}
      {showAssign && (
        <div
          className="modal-overlay open"
          onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
          onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) setShowAssign(false); }}
        >
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Assign Asset</span>
              <button className="modal-close" onClick={() => setShowAssign(false)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body flex flex-col gap-4">
              {assignError && <div className="alert alert-error">{assignError}</div>}

              <div className="field-group">
                <label className="field-label">Asset *</label>
                <select
                  className="field-input field-select"
                  value={assignForm.asset}
                  onChange={e => setAssignForm(f => ({ ...f, asset: e.target.value }))}
                >
                  <option value="">Select an available asset…</option>
                  {availableAssets.map(a => (
                    <option key={a.id} value={a.id}>{a.asset_tag} — {a.asset_name}</option>
                  ))}
                </select>
                {availableAssets.length === 0 && (
                  <p className="field-help" style={{ marginTop: 4 }}>No available assets in scope right now.</p>
                )}
              </div>

              <div className="field-group">
                <label className="field-label">Assigned Date *</label>
                <input
                  className="field-input" type="date"
                  value={assignForm.assigned_date}
                  onChange={e => setAssignForm(f => ({ ...f, assigned_date: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Condition at Assignment *</label>
                <select
                  className="field-input field-select"
                  value={assignForm.condition_at_assignment}
                  onChange={e => setAssignForm(f => ({ ...f, condition_at_assignment: e.target.value as AssetCondition }))}
                >
                  {ASSET_CONDITION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">Expected Return Date <span className="text-muted">(optional)</span></label>
                <input
                  className="field-input" type="date"
                  value={assignForm.expected_return_date}
                  onChange={e => setAssignForm(f => ({ ...f, expected_return_date: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Remarks <span className="text-muted">(optional)</span></label>
                <textarea
                  className="field-input"
                  value={assignForm.remarks}
                  onChange={e => setAssignForm(f => ({ ...f, remarks: e.target.value }))}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setShowAssign(false)} disabled={assigning}>Cancel</button>
              <button className="btn btn-filled" onClick={submitAssign} disabled={assigning}>
                {assigning ? <><i className="ti ti-loader-2 spin" /> Assigning…</> : "Assign Asset"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Return modal ── */}
      {returnTarget && (
        <div
          className="modal-overlay open"
          onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
          onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) setReturnTarget(null); }}
        >
          <div className="modal">
            <div className="modal-header">
              <span className="modal-title">Return Asset — {returnTarget.asset_tag}</span>
              <button className="modal-close" onClick={() => setReturnTarget(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body flex flex-col gap-4">
              {returnError && <div className="alert alert-error">{returnError}</div>}

              <div className="field-group">
                <label className="field-label">Return Date *</label>
                <input
                  className="field-input" type="date"
                  value={returnForm.return_date}
                  onChange={e => setReturnForm(f => ({ ...f, return_date: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Return Condition *</label>
                <select
                  className="field-input field-select"
                  value={returnForm.return_condition}
                  onChange={e => setReturnForm(f => ({ ...f, return_condition: e.target.value as AssetCondition }))}
                >
                  {ASSET_CONDITION_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>

              <div className="field-group">
                <label className="field-label">Return Reason *</label>
                <textarea
                  className="field-input"
                  placeholder="e.g. Employee offboarding, equipment upgrade, damaged…"
                  value={returnForm.return_reason}
                  onChange={e => setReturnForm(f => ({ ...f, return_reason: e.target.value }))}
                />
              </div>

              <div className="field-group">
                <label className="field-label">Remarks <span className="text-muted">(optional)</span></label>
                <textarea
                  className="field-input"
                  value={returnForm.remarks}
                  onChange={e => setReturnForm(f => ({ ...f, remarks: e.target.value }))}
                />
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setReturnTarget(null)} disabled={returning}>Cancel</button>
              <button className="btn btn-filled" onClick={submitReturn} disabled={returning}>
                {returning ? <><i className="ti ti-loader-2 spin" /> Returning…</> : "Return Asset"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
