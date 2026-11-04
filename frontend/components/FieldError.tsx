// Inline, field-specific validation message (styled by .field-error-msg in globals.css).
export default function FieldError({ msg }: { msg?: string | null }) {
  return msg ? <div className="field-error-msg" role="alert">{msg}</div> : null;
}
