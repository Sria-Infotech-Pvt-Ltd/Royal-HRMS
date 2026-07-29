"use client";

import { useState } from "react";
import {
  validateRoleForm,
  type ApiRole, type PermissionsMap, type RoleForm, type RoleFormErrors,
} from "../_data";
import RoleFormFields from "./RoleFormFields";

interface Props {
  role: ApiRole;
  permissionsMap: PermissionsMap;
  saving: boolean;
  onClose: () => void;
  onEdit: (form: RoleForm) => Promise<void>;
}

export default function EditRoleModal({ role, permissionsMap, saving, onClose, onEdit }: Props) {
  const [form, setForm]     = useState<RoleForm>({
    display_name:        role.display_name,
    can_manage_team:     role.can_manage_team,
    permission_codenames: role.permissions,
  });
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
    await onEdit(form);
  }

  function handleBackdrop(e: React.MouseEvent<HTMLDivElement>) {
    if (e.target === e.currentTarget) onClose();
  }

  return (
    <div className="modal-overlay open" onClick={handleBackdrop}>
      <div className="modal modal-lg">

        <div className="modal-header">
          <div>
            <div className="modal-title">Edit Role</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
              Updating permissions will take effect immediately for all users in this role
            </div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">

          {/* Read-only slug */}
          <div className="field-group mb-16">
            <label className="field-label">
              Role Slug <span style={{ fontSize: 10, color: "var(--outline)", marginLeft: 4 }}>read-only</span>
            </label>
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "9px 12px", border: "1.5px solid var(--outline-v)", borderRadius: "var(--radius)", background: "var(--bg-low)" }}>
              <i className="ti ti-lock" style={{ fontSize: 14, color: "var(--outline)", flexShrink: 0 }} />
              <code style={{ fontSize: 13, color: "var(--on-variant)" }}>{role.name}</code>
            </div>
          </div>

          <RoleFormFields
            form={form}
            errors={errors}
            permissionsMap={permissionsMap}
            onChange={patch}
            onClearError={clearError}
          />
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={saving}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>
            }
          </button>
        </div>

      </div>
    </div>
  );
}
