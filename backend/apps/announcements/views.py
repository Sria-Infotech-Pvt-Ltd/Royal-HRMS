from __future__ import annotations

import logging

from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Prefetch, Q, QuerySet, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.views import APIView
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog
from apps.announcements.models import Announcement, AnnouncementReaction
from apps.announcements.serializers import AnnouncementSerializer, AnnouncementWriteSerializer
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)


def _mark_announcement_notification_read(user, announcement_id: int) -> None:
    """
    _on_announcement_save (apps/notifications/signals.py) creates one bell
    notification per visible user when an announcement is posted, linked back
    via module='announcement' + reference_id=<announcement.id>. Nothing
    previously resolved that link when the announcement was actually opened,
    so it stayed "unread" in the bell dropdown forever even after reading it.
    """
    Notification.objects.filter(
        user=user, module='announcement', reference_id=str(announcement_id), is_read=False,
    ).update(is_read=True)


# ─── Permission ───────────────────────────────────────────────────────────────

class CanPostAnnouncement(BasePermission):
    """
    Safe methods: any authenticated user.
    Write methods: gated by the announcements.create/edit/delete codenames —
    NOT a hardcoded role set, so this always matches whatever Roles &
    Permissions actually grants (today: hr_admin, system_admin only).
    Object-level edit/delete: system_admin can modify any; others only their own.
    """

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if view.__class__.__name__ == 'AnnouncementListCreateView':
            return _has_perm(request.user, 'announcements.create')
        if request.method == 'DELETE':
            return _has_perm(request.user, 'announcements.delete')
        return _has_perm(request.user, 'announcements.edit')

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        # _has_perm (core.permissions.has_perm) already checks the superuser
        # bypass before its own role-null guard — a redundant `if not
        # request.user.role` check here used to run first and deny a
        # superuser with no linked Role row before _has_perm ever got a
        # chance to bypass it.
        if _has_perm(request.user, 'settings.edit'):
            return True
        return obj.posted_by_id == request.user.id


# ─── Queryset builder ─────────────────────────────────────────────────────────

def _visible_qs(request) -> 'QuerySet[Announcement]':
    """Return the base Announcement queryset scoped to what `request.user` may see."""
    if _has_perm(request.user, 'announcements.edit'):
        qs = Announcement.objects.all()
    else:
        qs = Announcement.objects.filter(
            Q(visibility=Announcement.VISIBILITY_ALL)
            | Q(visibility=Announcement.VISIBILITY_DEPARTMENT,
                target_department__name=request.user.department)
            | Q(visibility=Announcement.VISIBILITY_BRANCH,
                target_branch__branch_name=request.user.branch)
        )

    # Meta.ordering alone isn't enough here — annotate() below adds a GROUP BY,
    # which makes Django treat the queryset as unordered unless order_by() is
    # called explicitly. Without this, pagination can show duplicate or
    # skipped rows as the underlying table changes between page requests.
    return qs.annotate(
        reaction_count=Count('reactions', distinct=True)
    ).order_by('-is_pinned', '-created_at').prefetch_related(
        Prefetch(
            'reactions',
            queryset=AnnouncementReaction.objects.filter(user=request.user),
            to_attr='_user_reactions',
        )
    ).select_related('posted_by', 'posted_by__role', 'target_department', 'target_branch')


# ─── Views ────────────────────────────────────────────────────────────────────

class AnnouncementListCreateView(APIView):
    permission_classes = [IsAuthenticated, CanPostAnnouncement]

    def get(self, request):
        qs = _visible_qs(request)

        # ── Filters ───────────────────────────────────────────────────────────
        if category := request.query_params.get('category'):
            if category in dict(Announcement.CATEGORY_CHOICES):
                qs = qs.filter(category=category)

        # ── Stats (computed on the un-paginated, un-category-filtered set) ───
        base_qs     = _visible_qs(request)
        total_count = base_qs.count()
        pinned_count = base_qs.filter(is_pinned=True).count()
        total_views = base_qs.aggregate(v=Sum('views_count'))['v'] or 0
        total_reactions = AnnouncementReaction.objects.filter(
            announcement__in=base_qs
        ).count()

        # ── Pagination ────────────────────────────────────────────────────────
        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 10))))
        except (ValueError, TypeError):
            page_num, page_size = 1, 10

        paginator   = Paginator(qs, page_size)
        page_obj    = paginator.get_page(page_num)

        serializer  = AnnouncementSerializer(
            page_obj.object_list, many=True, context={'request': request}
        )

        return success('Announcements fetched.', {
            'count':           total_count,
            'page':            page_obj.number,
            'page_size':       page_size,
            'total_pages':     paginator.num_pages,
            'pinned_count':    pinned_count,
            'total_reactions': total_reactions,
            'total_views':     total_views,
            'results':         serializer.data,
        })

    @transaction.atomic
    def post(self, request):
        serializer = AnnouncementWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        data = serializer.validated_data
        announcement = Announcement.objects.create(
            title             = data['title'],
            body              = data['body'],
            category          = data['category'],
            visibility        = data['visibility'],
            target_department = data.get('target_department'),
            target_branch     = data.get('target_branch'),
            is_pinned         = data.get('is_pinned', False),
            send_email        = data.get('send_email', False),
            posted_by         = request.user,
        )

        AuditLog.objects.create(
            user       = request.user,
            action     = 'announcement_created',
            module     = 'announcements',
            object_id  = str(announcement.pk),
            changes    = {'title': announcement.title, 'category': announcement.category,
                          'visibility': announcement.visibility},
            ip_address = get_client_ip(request),
        )

        if announcement.send_email:
            from django.db import connection
            from apps.announcements.tasks import send_announcement_email_task

            def _queue_announcement_email(ann_id=announcement.id, schema_name=connection.schema_name):
                # Runs after the transaction actually commits, so the worker
                # (a separate DB connection) is guaranteed to find the row.
                # Queuing failure (e.g. broker down) is logged, not raised —
                # the announcement itself has already been saved successfully.
                try:
                    # retry=False + ignore_result=True — see the identical
                    # fix on the referral-submission dispatch in
                    # apps/recruitment/views.py for why: apply_async()
                    # otherwise subscribes to a Redis pub/sub result channel
                    # nothing here reads, retrying up to 20 times against the
                    # result backend if Redis is unreachable and blocking
                    # this request for well past any frontend timeout.
                    send_announcement_email_task.apply_async(
                        args=[schema_name, ann_id], retry=False, ignore_result=True,
                    )
                except Exception as exc:
                    logger.error(
                        'Failed to queue announcement email for %s: %s',
                        ann_id, exc, exc_info=True,
                    )

            transaction.on_commit(_queue_announcement_email)

        out = AnnouncementSerializer(announcement, context={'request': request})
        return success('Announcement posted.', out.data, http_status=status.HTTP_201_CREATED)


class AnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated, CanPostAnnouncement]

    def _get_object(self, request, pk: int) -> Announcement:
        qs  = _visible_qs(request)
        obj = get_object_or_404(qs, pk=pk)
        self.check_object_permissions(request, obj)
        return obj

    def get(self, request, pk: int):
        ann = self._get_object(request, pk)
        # Increment view count atomically (exclude the poster's own views)
        if ann.posted_by_id != request.user.id:
            Announcement.objects.filter(pk=pk).update(views_count=F('views_count') + 1)
            ann.views_count += 1
        _mark_announcement_notification_read(request.user, pk)
        serializer = AnnouncementSerializer(ann, context={'request': request})
        return success('Announcement fetched.', serializer.data)

    @transaction.atomic
    def put(self, request, pk: int):
        ann        = self._get_object(request, pk)
        serializer = AnnouncementWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        data = serializer.validated_data
        ann.title             = data['title']
        ann.body              = data['body']
        ann.category          = data['category']
        ann.visibility        = data['visibility']
        ann.target_department = data.get('target_department')
        ann.target_branch     = data.get('target_branch')
        ann.is_pinned         = data.get('is_pinned', False)
        ann.send_email        = data.get('send_email', False)
        ann.save()

        AuditLog.objects.create(
            user       = request.user,
            action     = 'announcement_updated',
            module     = 'announcements',
            object_id  = str(ann.pk),
            changes    = {'title': ann.title, 'category': ann.category,
                          'visibility': ann.visibility},
            ip_address = get_client_ip(request),
        )

        out = AnnouncementSerializer(ann, context={'request': request})
        return success('Announcement updated.', out.data)

    @transaction.atomic
    def patch(self, request, pk: int):
        ann        = self._get_object(request, pk)
        serializer = AnnouncementWriteSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        data = serializer.validated_data
        for field in ('title', 'body', 'category', 'visibility', 'is_pinned', 'send_email'):
            if field in data:
                setattr(ann, field, data[field])
        if 'target_department' in data:
            ann.target_department = data.get('target_department')
        if 'target_branch' in data:
            ann.target_branch = data.get('target_branch')
        ann.save()

        AuditLog.objects.create(
            user       = request.user,
            action     = 'announcement_updated',
            module     = 'announcements',
            object_id  = str(ann.pk),
            changes    = {k: str(v) for k, v in data.items()},
            ip_address = get_client_ip(request),
        )

        out = AnnouncementSerializer(ann, context={'request': request})
        return success('Announcement updated.', out.data)

    def post(self, request, pk: int):
        return self.put(request, pk)

    @transaction.atomic
    def delete(self, request, pk: int):
        ann = self._get_object(request, pk)
        ann_title = ann.title
        ann_id    = ann.pk
        ann.delete()

        AuditLog.objects.create(
            user       = request.user,
            action     = 'announcement_deleted',
            module     = 'announcements',
            object_id  = str(ann_id),
            changes    = {'title': ann_title},
            ip_address = get_client_ip(request),
        )

        return success('Announcement deleted.')


class AnnouncementReactView(APIView):
    """Toggle a like reaction on an announcement. One reaction per user."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        announcement = get_object_or_404(
            Announcement.objects.filter(
                Q(visibility=Announcement.VISIBILITY_ALL)
                | Q(visibility=Announcement.VISIBILITY_DEPARTMENT,
                    target_department__name=request.user.department)
                | Q(visibility=Announcement.VISIBILITY_BRANCH,
                    target_branch__branch_name=request.user.branch)
            ) if not _has_perm(request.user, 'announcements.edit')
            else Announcement.objects.all(),
            pk=pk,
        )

        reaction, created = AnnouncementReaction.objects.get_or_create(
            announcement=announcement,
            user=request.user,
        )
        if not created:
            reaction.delete()
            has_reacted = False
        else:
            has_reacted = True

        reactions_count = announcement.reactions.count()
        return success('Reaction updated.', {
            'has_reacted':    has_reacted,
            'reactions_count': reactions_count,
        })


class AnnouncementViewTrackView(APIView):
    """Increment view count. Called by the frontend once per card per session."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        if not Announcement.objects.filter(pk=pk).exists():
            return error('Announcement not found.', http_status=status.HTTP_404_NOT_FOUND)
        # Only count views from non-authors; silently skip if user is the author
        Announcement.objects.filter(pk=pk).exclude(
            posted_by=request.user
        ).update(views_count=F('views_count') + 1)
        _mark_announcement_notification_read(request.user, pk)
        return success('View recorded.')
