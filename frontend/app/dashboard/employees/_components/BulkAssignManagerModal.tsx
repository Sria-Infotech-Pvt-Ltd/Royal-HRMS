"use client";

// HR picks employees who have no reporting manager, chooses one manager, and assigns them all in one go. The server skips
// (with a reason) anyone it cannot change, and writes an audit entry per change.

import { useMemo, useState } from "react";
import Modal from "@/components/Modal";
import FieldError from "@/components/shared/FieldError";
import { useToast } from "@/components/ToastProvider";
import { useFetch } from "@/hooks/useFetch";
import { useApiErrors } from "@/hooks/useApiErrors";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { rowsOf } from "@/lib/listResponse";
import type { ApiEmployee } from "../[id]/_apiMapping";

interface ManagerOption { id: string; employee_id: string; full_name: string; department: string | null }
interface AssignResult { assigned: string[]; skipped: { employee_id: string; reason: string }[] }
interface BulkAssignManagerModalProps { onClose: () => void; onDone: () => void }

const EMPLOYEE_LIST_URL = `${API.employees.list}?page_size=200`;
const MANAGER_LIST_URL = `${API.employees.managerList}?all=true`;

export default function BulkAssignManagerModal({ onClose, onDone }: BulkAssignManagerModalProps) {
  const { showToast } = useToast();
  const { fieldErrors, handleError, clearAll } = useApiErrors();
  const { data: employeePage, loading: isLoadingEmployees } = useFetch<{ results: ApiEmployee[] }>(EMPLOYEE_LIST_URL);
  const { data: managers } = useFetch<ManagerOption[]>(MANAGER_LIST_URL);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [managerId, setManagerId] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [skipped, setSkipped] = useState<AssignResult["skipped"]>([]);

  // Only people who are meant to have a manager (the key is absent for managers) and have none resolved.
  const withoutManager = useMemo(
    () => rowsOf<ApiEmployee>(employeePage).filter(person => "reporting_manager" in person && !person.reporting_manager?.name),
    [employeePage],
  );

  function toggle(code: string) {
    setSelected(previous => {
      const next = new Set(previous);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  }

  async function submit() {
    clearAll();
    setIsSaving(true);
    try {
      const { data } = await clientApi.post<{ data: AssignResult }>(API.employees.bulkAssignManager, {
        manager_id: managerId, employee_ids: [...selected],
      });
      showToast(`${data.data.assigned.length} employee(s) assigned.`, "success");
      setSkipped(data.data.skipped);
      setSelected(new Set());
      onDone();
      if (data.data.skipped.length === 0) onClose();
    } catch (err: unknown) {
      handleError(err, "Could not assign the manager.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      title={<div className="text-[18px] font-bold">Assign <span style={{ color: "var(--primary)", fontStyle: "italic" }}>reporting manager</span></div>}
      onClose={onClose}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={isSaving}>Close</button>
          <button className="btn btn-filled" type="button" onClick={submit} disabled={isSaving || selected.size === 0 || !managerId}>
            {isSaving ? "Assigning…" : `Assign to ${selected.size} employee(s)`}
          </button>
        </>
      }
    >
      <div style={{ display: "grid", gap: 14 }}>
        <div className="f">
          <label htmlFor="bulk-manager">Reporting manager</label>
          <select id="bulk-manager" className="finput" value={managerId} onChange={event => setManagerId(event.target.value)}>
            <option value="">Select a manager</option>
            {(managers ?? []).map(manager => (
              <option key={manager.id} value={manager.employee_id}>{manager.full_name} ({manager.employee_id})</option>
            ))}
          </select>
          <FieldError message={fieldErrors.manager_id} />
        </div>

        <div>
          <div className="flex items-center justify-between" style={{ marginBottom: 6 }}>
            <b style={{ fontSize: 13 }}>Employees with no reporting manager ({withoutManager.length})</b>
            {withoutManager.length > 0 && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setSelected(new Set(withoutManager.map(person => person.employee_id)))}>
                Select all
              </button>
            )}
          </div>
          <FieldError message={fieldErrors.employee_ids} />
          {isLoadingEmployees ? (
            <p className="hint">Loading…</p>
          ) : withoutManager.length === 0 ? (
            <p className="hint">Everyone who should have a reporting manager has one.</p>
          ) : (
            <div style={{ maxHeight: 280, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
              {withoutManager.map(person => (
                <label key={person.employee_id} className="flex items-center gap-2" style={{ padding: "8px 12px", cursor: "pointer", fontSize: 13 }}>
                  <input type="checkbox" checked={selected.has(person.employee_id)} onChange={() => toggle(person.employee_id)} />
                  <span>{person.full_name}</span>
                  <span style={{ color: "var(--on-variant)" }}>{person.employee_id}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        {skipped.length > 0 && (
          <div className="alert alert-warning" role="status">
            <i className="ti ti-alert-triangle" />
            <div>{skipped.length} could not be changed: {skipped.map(item => `${item.employee_id} (${item.reason})`).join("; ")}</div>
          </div>
        )}
      </div>
    </Modal>
  );
}
