"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import Modal from "@/components/Modal";
import SearchableSelect from "@/components/SearchableSelect";
import { type PickerEmployee, SELECT_CLS } from "./approvalMatrixShared";

interface RelationshipEditorProps {
  title:        string;
  listEndpoint: string;
  currentId:    string;
  saveEndpoint: string;
  bodyKey:      string;
  onSaved:      (id: string, name: string, empId: string) => void;
  onClose:      () => void;
}

export default function RelationshipEditorModal({
  title, listEndpoint, currentId, saveEndpoint, bodyKey, onSaved, onClose,
}: RelationshipEditorProps) {
  const [selectedId, setSelectedId] = useState(currentId);
  const [saving,     setSaving]     = useState(false);
  const [apiError,   setApiError]   = useState("");

  const { data: listRaw, loading } = useFetch<PickerEmployee[]>(listEndpoint);
  const people = listRaw ?? [];

  async function handleSave() {
    if (!selectedId) return;
    setSaving(true);
    setApiError("");
    try {
      await clientApi.patch(saveEndpoint, { [bodyKey]: selectedId });
      const person = people.find(p => p.id === selectedId);
      onSaved(selectedId, person?.full_name ?? "", person?.employee_id ?? "");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={title}
      onClose={onClose}
      maxWidth={440}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className="btn btn-filled"
            onClick={handleSave}
            disabled={saving || !selectedId || loading}
          >
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save"}
          </button>
        </>
      }
    >
      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {apiError}
        </div>
      )}
      <div className="field-group">
        <label className="field-label">Select person</label>
        <SearchableSelect
          value={selectedId}
          onChange={setSelectedId}
          disabled={loading}
          inputClassName={SELECT_CLS}
          placeholder={loading ? "Loading…" : "— Select —"}
          options={people.map(p => ({ value: p.id, label: `${p.full_name} (${p.employee_id})` }))}
        />
      </div>
    </Modal>
  );
}
