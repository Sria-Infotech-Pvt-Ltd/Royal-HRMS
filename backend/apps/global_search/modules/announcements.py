"""Announcements: exactly the ones the Announcements page shows this viewer (visible_announcements)."""
from apps.announcements.models import Announcement
from apps.announcements.services_announcements_visibility import visible_announcements
from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec, SearchModule, register

from ._helpers import choices_of, label_of, short_date


def _queryset(user):
    return visible_announcements(user).select_related('posted_by', 'target_branch', 'target_org_unit')


def _describe(announcement: Announcement) -> dict:
    return {
        'id': str(announcement.pk), 'title': announcement.title,
        'subtitle': ' · '.join(part for part in (label_of(announcement, 'category'), short_date(announcement.created_at)) if part),
        'meta': {'Audience': label_of(announcement, 'visibility'), 'Posted by': announcement.posted_by.full_name if announcement.posted_by_id else ''},
        'url': '/dashboard/announcements',
    }


ANNOUNCEMENTS = register(SearchModule(
    key='announcements', label='Announcements', icon='ti-speakerphone', permission=None, queryset=_queryset,
    fields=(
        FieldSpec('title', 'Title', f.TEXT, 'title', searchable=True),
        FieldSpec('body', 'Message', f.TEXT, 'body', searchable=True),
        FieldSpec('category', 'Category', f.CHOICE, 'category', choices=choices_of(Announcement, 'category')),
        FieldSpec('visibility', 'Audience', f.CHOICE, 'visibility', choices=choices_of(Announcement, 'visibility')),
        FieldSpec('is_pinned', 'Pinned', f.BOOLEAN, 'is_pinned'),
        FieldSpec('posted_by', 'Posted by', f.TEXT, 'posted_by__full_name'),
        FieldSpec('created_at', 'Posted on', f.DATETIME, 'created_at'),
    ),
    describe=_describe, order_by=('-is_pinned', '-created_at', '-pk'), default_url='/dashboard/announcements',
))
