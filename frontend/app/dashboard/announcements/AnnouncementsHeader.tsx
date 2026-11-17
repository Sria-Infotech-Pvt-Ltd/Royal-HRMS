"use client";

interface AnnouncementsHeaderProps {
  onBack: () => void
}

/** Title and a way back. (Posting is offered from the empty-state card, not from here.) */
export default function AnnouncementsHeader({ onBack }: AnnouncementsHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <div className="page-title">Announcements</div>
        <div className="page-sub">Company-wide news, policy updates, and celebrations</div>
      </div>
      <div className="page-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>
    </div>
  )
}
