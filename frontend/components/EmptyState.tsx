"use client";

// Shared "no data yet" block — extends the existing `.empty-state` class in
// app/globals.css rather than inventing a new look. Replaces the many
// hand-rolled versions of this same block scattered across the app (each
// with its own separately-tuned padding/icon size/copy) with one component,
// so every list/tab that has nothing to show looks and behaves the same way.

interface Props {
  icon?: string;       // tabler icon class suffix, e.g. "ti-inbox" — defaults to a generic one
  title: string;
  description?: string;
  action?: React.ReactNode; // optional button/link, e.g. "Add your first X"
}

export default function EmptyState({ icon = "ti-inbox", title, description, action }: Props) {
  return (
    <div className="empty-state">
      <i className={`ti ${icon}`} />
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}
