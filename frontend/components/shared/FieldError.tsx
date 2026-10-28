interface Props {
  message?: string | null;
}

/** The server's (or the form's) message for one field, shown right under its input. */
export default function FieldError({ message }: Props) {
  if (!message) return null;
  return <p className="field-error-msg" role="alert">{message}</p>;
}
