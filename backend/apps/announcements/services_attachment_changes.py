"""Apply the attachment and link part of an announcement save: remove what was removed, add what was uploaded, update the links.

Runs inside the caller's database transaction. Files removed from storage only after that transaction commits, so a save that is
rolled back never loses a file it was supposed to keep.
"""
from __future__ import annotations

from django.db import transaction

from apps.announcements.models import Announcement, AnnouncementAttachment
from apps.announcements.services_attachments import check_counts, delete_stored_files, store_new_files


def precheck(announcement: Announcement | None, *, images: list, documents: list, remove_ids: set) -> None:
    """Fail before anything is written if the change would break a limit (or names an attachment that is not this announcement's)."""
    existing = list(announcement.attachments.all()) if announcement is not None else []
    check_counts(existing, remove_ids, images, documents)


def apply_changes(
    announcement: Announcement, *, images: list, documents: list, remove_ids: set, links: list | None,
) -> dict:
    """Make the change. `links` is None when the request did not mention links (they are then left exactly as they are)."""
    precheck(announcement, images=images, documents=documents, remove_ids=remove_ids)
    removed_names = []
    if remove_ids:
        doomed = list(announcement.attachments.filter(pk__in=remove_ids))
        removed_names = [attachment.file.name for attachment in doomed]
        AnnouncementAttachment.objects.filter(pk__in=[attachment.pk for attachment in doomed]).delete()
    created = store_new_files(announcement, images, documents)
    if links is not None:
        announcement.links = links
        announcement.save(update_fields=['links', 'updated_at'])
    # The caller may hold this announcement with its attachments already loaded (the list queryset prefetches them); drop that copy
    # so the response built afterwards shows the attachments as they are now, not as they were before this change.
    getattr(announcement, '_prefetched_objects_cache', {}).pop('attachments', None)
    if removed_names:
        transaction.on_commit(lambda: delete_stored_files(removed_names))
    return {'attachments_added': len(created), 'attachments_removed': len(removed_names)}
