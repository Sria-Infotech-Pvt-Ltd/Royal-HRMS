// What Edit full record sends for the contact fields: only what HR actually changed, and never for a role that may not edit.

interface ContactDraft {
  personalEmail: string;
  mobileNumber: string;
}

interface SavedContact {
  email: string;
  mobile: string;
}

export interface ContactChanges {
  email?: string;
  confirm_login_email_change?: boolean;
  phone?: string;
}

function lastTenDigits(value: string): string {
  return value.replace(/\D/g, "").slice(-10);
}

export function buildContactChanges(
  draft: ContactDraft,
  saved: SavedContact,
  canEdit: boolean,
  isLoginChangeConfirmed: boolean,
): ContactChanges {
  if (!canEdit) return {};
  const changes: ContactChanges = {};
  if (draft.personalEmail.trim().toLowerCase() !== saved.email.trim().toLowerCase()) {
    changes.email = draft.personalEmail.trim();
    changes.confirm_login_email_change = isLoginChangeConfirmed;
  }
  // A blank mobile is sent too, so the server can say it is required rather than the edit being silently dropped.
  if (lastTenDigits(draft.mobileNumber) !== lastTenDigits(saved.mobile) || !draft.mobileNumber.trim()) {
    changes.phone = draft.mobileNumber;
  }
  return changes;
}
