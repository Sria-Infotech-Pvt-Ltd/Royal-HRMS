"""Phase 8B gap-closure — scheduling/expiry/pinned-until/drafts, translations."""
from django.db import transaction
from django.utils import timezone

from apps.announcements.models import Announcement, AnnouncementSchedule, AnnouncementTranslation


def set_schedule(announcement: Announcement, *, publish_at=None, expire_at=None, pinned_until=None, is_draft=False) -> AnnouncementSchedule:
    schedule, _ = AnnouncementSchedule.objects.update_or_create(
        announcement=announcement,
        defaults={'publish_at': publish_at, 'expire_at': expire_at, 'pinned_until': pinned_until, 'is_draft': is_draft},
    )
    return schedule


def is_currently_visible(announcement: Announcement) -> bool:
    """The real "drafts/scheduling/expiry" gate — an Announcement with no
    schedule row is always visible (matches today's unconditional
    behavior exactly, zero change for anything not yet scheduled)."""
    schedule = getattr(announcement, 'schedule', None)
    if schedule is None:
        return True
    if schedule.is_draft:
        return False
    now = timezone.now()
    if schedule.publish_at and now < schedule.publish_at:
        return False
    if schedule.expire_at and now > schedule.expire_at:
        return False
    return True


def visible_announcements():
    return [a for a in Announcement.objects.all() if is_currently_visible(a)]


def set_translation(announcement: Announcement, language_code: str, title: str, body: str) -> AnnouncementTranslation:
    translation, _ = AnnouncementTranslation.objects.update_or_create(
        announcement=announcement, language_code=language_code, defaults={'title': title, 'body': body},
    )
    return translation


def localized_content(announcement: Announcement, language_code: str) -> dict:
    translation = announcement.translations.filter(language_code=language_code).first()
    if translation is None:
        return {'title': announcement.title, 'body': announcement.body}
    return {'title': translation.title, 'body': translation.body}
