from __future__ import annotations

import logging

from rest_framework import serializers

from core.permissions import has_perm as _has_perm

from apps.accounts.models import OrgUnit
from apps.branch.models import Branch

from .models import Announcement, AnnouncementAttachment
from .services_attachments import AttachmentError, check_upload, clean_links

logger = logging.getLogger(__name__)


class AnnouncementAttachmentSerializer(serializers.ModelSerializer):
    """An attachment as the viewer sees it. `url` (images only) is a short-lived signed address for showing the picture;
    `download_path` is the authorised endpoint (relative to the API root) that every download goes through."""

    url           = serializers.SerializerMethodField()
    download_path = serializers.SerializerMethodField()

    class Meta:
        model  = AnnouncementAttachment
        fields = ['id', 'attachment_type', 'original_filename', 'file_size', 'content_type', 'url', 'download_path']

    def get_url(self, obj: AnnouncementAttachment) -> str:
        if obj.attachment_type != AnnouncementAttachment.TYPE_IMAGE:
            return ''
        try:
            return obj.file.url
        except Exception:  # a storage hiccup must not break the whole announcement list
            logger.exception('Could not build an image URL for announcement attachment %s.', obj.pk)
            return ''

    def get_download_path(self, obj: AnnouncementAttachment) -> str:
        return f'/announcements/{obj.announcement_id}/attachments/{obj.pk}/download/'


class AnnouncementSerializer(serializers.ModelSerializer):
    """Read serializer — includes all computed fields needed by the frontend."""

    posted_by_name        = serializers.SerializerMethodField()
    posted_by_role        = serializers.SerializerMethodField()
    reactions_count       = serializers.SerializerMethodField()
    has_reacted           = serializers.SerializerMethodField()
    target_org_unit_name  = serializers.SerializerMethodField()
    target_branch_name    = serializers.SerializerMethodField()
    can_edit              = serializers.SerializerMethodField()
    attachments           = AnnouncementAttachmentSerializer(many=True, read_only=True)
    links                 = serializers.JSONField(read_only=True)

    class Meta:
        model  = Announcement
        fields = [
            'id', 'title', 'body', 'category', 'visibility',
            'target_org_unit', 'target_org_unit_name',
            'target_branch', 'target_branch_name',
            'is_pinned', 'send_email',
            'posted_by', 'posted_by_name', 'posted_by_role',
            'views_count', 'reactions_count', 'has_reacted',
            'can_edit', 'attachments', 'links', 'created_at', 'updated_at',
        ]

    # ── posted_by fields ──────────────────────────────────────────────────────

    def get_posted_by_name(self, obj: Announcement) -> str:
        return obj.posted_by.full_name if obj.posted_by_id else 'Former Employee'

    def get_posted_by_role(self, obj: Announcement) -> str:
        return (obj.posted_by.designation or '') if obj.posted_by_id else ''

    # ── target labels ─────────────────────────────────────────────────────────

    def get_target_org_unit_name(self, obj: Announcement) -> str:
        return obj.target_org_unit.name if obj.target_org_unit_id else ''

    def get_target_branch_name(self, obj: Announcement) -> str:
        return obj.target_branch.branch_name if obj.target_branch_id else ''

    # ── reaction helpers — use pre-fetched attrs when available ───────────────

    def get_reactions_count(self, obj: Announcement) -> int:
        # `reaction_count` is annotated by the view queryset
        if hasattr(obj, 'reaction_count'):
            return obj.reaction_count
        return obj.reactions.count()

    def get_has_reacted(self, obj: Announcement) -> bool:
        # `_user_reactions` is a Prefetch to_attr set by the view queryset
        user_reactions = getattr(obj, '_user_reactions', None)
        if user_reactions is not None:
            return bool(user_reactions)
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.reactions.filter(user=request.user).exists()

    # ── edit permission ───────────────────────────────────────────────────────

    def get_can_edit(self, obj: Announcement) -> bool:
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        user = request.user
        if _has_perm(user, 'settings.edit'):
            return True
        return obj.posted_by_id == user.id


class AnnouncementWriteSerializer(serializers.Serializer):
    """Write serializer — validates POST/PUT payloads."""

    title             = serializers.CharField(max_length=300)
    body              = serializers.CharField(max_length=10000)
    category          = serializers.ChoiceField(
                            choices=[c[0] for c in Announcement.CATEGORY_CHOICES]
                        )
    visibility        = serializers.ChoiceField(
                            choices=[c[0] for c in Announcement.VISIBILITY_CHOICES]
                        )
    target_org_unit   = serializers.PrimaryKeyRelatedField(
                            queryset=OrgUnit.objects.filter(is_active=True),
                            required=False, allow_null=True,
                        )
    target_branch     = serializers.PrimaryKeyRelatedField(
                            queryset=Branch.objects.filter(status=Branch.STATUS_ACTIVE),
                            required=False, allow_null=True,
                        )
    is_pinned         = serializers.BooleanField(default=False, required=False)
    send_email        = serializers.BooleanField(default=False, required=False)
    # Attachments (multipart/form-data): new files, links as a list or a JSON string, and ids of existing attachments to remove.
    images            = serializers.ListField(child=serializers.FileField(allow_empty_file=True), required=False)
    documents         = serializers.ListField(child=serializers.FileField(allow_empty_file=True), required=False)
    links             = serializers.JSONField(required=False)
    remove_attachment_ids = serializers.ListField(child=serializers.UUIDField(), required=False)

    def validate_images(self, files: list) -> list:
        return self._check_files(files, AnnouncementAttachment.TYPE_IMAGE)

    def validate_documents(self, files: list) -> list:
        return self._check_files(files, AnnouncementAttachment.TYPE_DOCUMENT)

    @staticmethod
    def _check_files(files: list, kind: str) -> list:
        for file in files:
            try:
                check_upload(file, kind)
            except AttachmentError as exc:
                raise serializers.ValidationError(str(exc)) from None
        return files

    def validate_links(self, value) -> list:
        try:
            return clean_links(value)
        except AttachmentError as exc:
            raise serializers.ValidationError(str(exc)) from None

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Announcement title is required.')
        return value

    def validate_body(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Announcement body is required.')
        return value

    def validate(self, data: dict) -> dict:
        visibility = data.get('visibility', Announcement.VISIBILITY_ALL)

        if visibility == Announcement.VISIBILITY_DEPARTMENT:
            if not data.get('target_org_unit'):
                raise serializers.ValidationError(
                    {'target_org_unit': 'An org unit must be selected when visibility is By Department.'}
                )
            data['target_branch'] = None

        elif visibility == Announcement.VISIBILITY_BRANCH:
            if not data.get('target_branch'):
                raise serializers.ValidationError(
                    {'target_branch': 'A branch must be selected when visibility is By Branch.'}
                )
            data['target_org_unit'] = None

        else:  # all
            data['target_org_unit'] = None
            data['target_branch']   = None

        return data
