"use client";

interface AnnouncementEmptyStateProps {
  /** A search, category, pinned switch or sort is narrowing the list. */
  hasFilters: boolean
  canPost:    boolean
  onCreate:   () => void
  onClear:    () => void
}

/** Two different empty screens: "nothing has been posted" and "nothing matches what you asked for". */
export default function AnnouncementEmptyState({ hasFilters, canPost, onCreate, onClear }: AnnouncementEmptyStateProps) {
  if (hasFilters) {
    return (
      <div className="ann-empty">
        <div className="ann-empty-icon"><i className="ti ti-search-off" /></div>
        <h3>No announcements match</h3>
        <p>Try a different word, another category, or turn off Pinned only.</p>
        <div className="ann-empty-actions">
          <button type="button" className="btn btn-filled" onClick={onClear}><i className="ti ti-filter-off" /> Clear filters</button>
        </div>
      </div>
    )
  }

  return (
    <div className="ann-empty">
      <div className="ann-empty-icon"><i className="ti ti-speakerphone" /></div>
      <h3>No announcements yet</h3>
      <p>
        {canPost
          ? "Share company news, policy updates or a celebration. You can pin important posts, attach images or PDFs and email everyone."
          : "When the company posts news, policy updates or celebrations, they will appear here."}
      </p>
      {canPost && (
        <div className="ann-empty-actions">
          <button type="button" className="btn btn-filled" onClick={onCreate}><i className="ti ti-plus" /> Post Announcement</button>
        </div>
      )}
    </div>
  )
}
