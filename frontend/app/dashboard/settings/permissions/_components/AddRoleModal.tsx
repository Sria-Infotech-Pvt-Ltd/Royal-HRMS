"use client";

import { useState } from "react";
import {
  EMPTY_ROLE_FORM, validateRoleForm,
  type PermissionsMap, type RoleForm, type RoleFormErrors,
} from "../_data";
import RoleFormFields from "./RoleFormFields";
import Modal from "@/components/Modal";

interface Props {
  permissionsMap: PermissionsMap;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onAdd: (form: RoleForm) => Promise<void>;
}

export default function AddRoleModal({ permissionsMap, saving, error, onClose, onAdd }: Props) {
  const [form, setForm]     = useState<RoleForm>(EMPTY_ROLE_FORM);
  const [errors, setErrors] = useState<RoleFormErrors>({});

  function patch(partial: Partial<RoleForm>) {
    setForm(prev => ({ ...prev, ...partial }));
  }

  function clearError(key: keyof RoleForm) {
    setErrors(prev => ({ ...prev, [key]: undefined }));
  }

  async function handleSubmit() {
    const errs = validateRoleForm(form);
    if (Object.keys(errs).length) { setErrors(errs); return; }
    await onAdd(form);
  }

  return (
    <Modal
      title="Add New Role"
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-plus" /> Add Role</>
            }
          </button>
        </>
      }
    >
      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{error}</div>
        </div>
      )}
      <RoleFormFields
        form={form}
        errors={errors}
        permissionsMap={permissionsMap}
        onChange={patch}
        onClearError={clearError}
      />
    </Modal>
  );
}
