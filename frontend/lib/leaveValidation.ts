// Shared client-side validation for leave type / credit rule display names.
// Mirrors _LEAVE_NAME_RE enforced server-side in backend/apps/hrms/serializers.py
// (LeavePolicyCreateSerializer.validate_leave_type_label).

export const LEAVE_NAME_RE = /^[A-Za-z][A-Za-z -]*$/;

export function sanitizeLeaveName(value: string): string {
  return value.replace(/[^A-Za-z -]/g, "");
}
