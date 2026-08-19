"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function InviteAdminModal({ onClose, onCreated }: Props) {
  const [email, setEmail]       = useState("");
  const [fullName, setFullName] = useState("");
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState("");
  const [invited, setInvited]   = useState(false);

  async function handleInvite() {
    setError("");
    if (!email.trim() || !fullName.trim()) {
      setError("Email and full name are both required.");
      return;
    }
    setSaving(true);
    try {
      await platformAdminApi.post(API.platformAdmin.admins.list, { email: email.trim(), full_name: fullName.trim() });
      setInvited(true);
      onCreated();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to invite platform admin.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  if (invited) {
    return (
      <Modal title="Invitation sent" onClose={onClose} maxWidth={420}
        footer={<button className="btn btn-filled" onClick={onClose} suppressHydrationWarning>Done</button>}>
        <div className="alert alert-success">
          <i className="ti ti-check" />
          <div><strong>{email.trim()}</strong> has been added as a platform admin, and their login details were emailed to them.</div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      title="Invite platform admin"
      onClose={onClose}
      maxWidth={440}
      closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
          <button className="btn btn-filled" onClick={handleInvite} disabled={saving} suppressHydrationWarning>
            {saving ? (<><i className="ti ti-loader-2 spin" /> Sending…</>) : "Send invite"}
          </button>
        </>
      }
    >
      {error && (
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <div>{error}</div>
        </div>
      )}
      <div className="field-group" style={{ marginBottom: 16 }}>
        <label className="field-label" htmlFor="ia-name">Full name</label>
        <input id="ia-name" className="field-input" placeholder="e.g. Priya Sharma" value={fullName}
          onChange={e => setFullName(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>
      <div className="field-group">
        <label className="field-label" htmlFor="ia-email">Email</label>
        <input id="ia-email" type="email" className="field-input" placeholder="admin@royalhrms.com" value={email}
          onChange={e => setEmail(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>
      <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 12 }}>
        A temporary password will be generated and emailed to them directly.
      </p>
    </Modal>
  );
}
