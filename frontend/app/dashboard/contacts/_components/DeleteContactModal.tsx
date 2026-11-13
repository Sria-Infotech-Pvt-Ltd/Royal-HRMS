"use client";

import Modal from "@/components/Modal";

interface Props {
  name: string;
  deleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

/** Confirms removing a Contact Matrix row — nothing is deleted until Delete is clicked. */
export default function DeleteContactModal({ name, deleting, onCancel, onConfirm }: Props) {
  return (
    <Modal
      title="Delete Contact"
      onClose={onCancel}
      closeDisabled={deleting}
      footer={<>
        <button className="btn btn-ghost" onClick={onCancel} disabled={deleting}>Cancel</button>
        <button className="btn btn-danger" onClick={onConfirm} disabled={deleting}>{deleting ? "Deleting…" : "Delete"}</button>
      </>}
    >
      <p style={{ margin: 0 }}>Remove <strong>{name}</strong> from the Contact Matrix?</p>
    </Modal>
  );
}
