"use client";

// Personal email + mobile in Edit full record. HR (employees.edit) can correct both; everyone else sees them read-only.
// The personal email is also the employee's login, so changing it needs an explicit tick and the employee is notified.

import PhoneInput from "@/components/PhoneInput";
import FieldError from "@/components/shared/FieldError";

interface EditRecordContactFieldsProps {
  canEdit: boolean;
  email: string;
  mobile: string;
  /** The email as stored, to know whether it was changed. */
  savedEmail: string;
  isLoginChangeConfirmed: boolean;
  emailError?: string;
  mobileError?: string;
  onEmailChange: (value: string) => void;
  onMobileChange: (value: string) => void;
  onLoginChangeConfirmed: (isConfirmed: boolean) => void;
}

const READ_ONLY_STYLE = { background: "var(--bg-low)", color: "var(--on-variant)" };
const HINT_STYLE = { color: "var(--on-variant)", fontWeight: 400 };

export default function EditRecordContactFields({
  canEdit, email, mobile, savedEmail, isLoginChangeConfirmed, emailError, mobileError,
  onEmailChange, onMobileChange, onLoginChangeConfirmed,
}: EditRecordContactFieldsProps) {
  const isEmailChanged = email.trim().toLowerCase() !== savedEmail.trim().toLowerCase();
  return (
    <>
      <div>
        <label className="block text-[12.5px] font-semibold mb-1.5">
          Personal email {!canEdit && <span style={HINT_STYLE}>read-only</span>}
        </label>
        <input
          type="email" value={email} readOnly={!canEdit} className="field-input"
          style={canEdit ? undefined : READ_ONLY_STYLE} onChange={event => onEmailChange(event.target.value)}
        />
        <FieldError message={emailError} />
        {canEdit && isEmailChanged && (
          <label className="flex items-start gap-2 text-[11.5px] mt-1.5" style={{ color: "var(--on-variant)" }}>
            <input
              type="checkbox" checked={isLoginChangeConfirmed} className="mt-0.5"
              onChange={event => onLoginChangeConfirmed(event.target.checked)}
            />
            <span>This is also the employee&apos;s login email. Changing it changes how they sign in, and they will be notified at the old and new address.</span>
          </label>
        )}
      </div>
      <div>
        <label className="block text-[12.5px] font-semibold mb-1.5">
          Mobile number {!canEdit && <span style={HINT_STYLE}>read-only</span>}
        </label>
        <PhoneInput value={mobile} onChange={canEdit ? onMobileChange : () => {}} placeholder="90000 00000" />
        <FieldError message={mobileError} />
      </div>
    </>
  );
}
