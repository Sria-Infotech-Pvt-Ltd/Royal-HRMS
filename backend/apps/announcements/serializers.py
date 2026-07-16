from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import Department
from apps.branch.models import Branch

from .models import Announcement, AnnouncementReaction


class AnnouncementSerializer(serializers.ModelSerializer):
    """Read serializer — includes all computed fields needed by the frontend."""

    posted_by_name        = serializers.SerializerMethodField()
    posted_by_role        = serializers.SerializerMethodField()
    reactions_count       = serializers.SerializerMethodField()
    has_reacted           = serializers.SerializerMethodField()
    target_department_name = serializers.SerializerMethodField()
    target_branch_name    = serializers.SerializerMethodField()
    can_edit              = serializers.SerializerMethodField()

    class Meta:
        model  = Announcement
        fields = [
            'id', 'title', 'body', 'category', 'visibility',
            'target_department', 'target_department_name',
            'target_branch', 'target_branch_name',
            'is_pinned', 'send_email',
            'posted_by', 'posted_by_name', 'posted_by_role',
            'views_count', 'reactions_count', 'has_reacted',
            'can_edit', 'created_at', 'updated_at',
        ]

    # ── posted_by fields ──────────────────────────────────────────────────────

    def get_posted_by_name(self, obj: Announcement) -> str:
        return obj.posted_by.full_name if obj.posted_by_id else 'Former Employee'

    def get_posted_by_role(self, obj: Announcement) -> str:
        if obj.posted_by_id and obj.posted_by.role:
            return obj.posted_by.role.display_name
        return ''

    # ── target labels ─────────────────────────────────────────────────────────

    def get_target_department_name(self, obj: Announcement) -> str:
        return obj.target_department.name if obj.target_department_id else ''

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
        if not user.role:
            return False
        if user.role.name == 'system_admin':
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
    target_department = serializers.PrimaryKeyRelatedField(
                            queryset=Department.objects.filter(is_active=True),
                            required=False, allow_null=True,
                        )
    target_branch     = serializers.PrimaryKeyRelatedField(
                            queryset=Branch.objects.filter(status=Branch.STATUS_ACTIVE),
                            required=False, allow_null=True,
                        )
    is_pinned         = serializers.BooleanField(default=False, required=False)
    send_email        = serializers.BooleanField(default=False, required=False)

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
            if not data.get('target_department'):
                raise serializers.ValidationError(
                    {'target_department': 'A department must be selected when visibility is By Department.'}
                )
            data['target_branch'] = None

        elif visibility == Announcement.VISIBILITY_BRANCH:
            if not data.get('target_branch'):
                raise serializers.ValidationError(
                    {'target_branch': 'A branch must be selected when visibility is By Branch.'}
                )
            data['target_department'] = None

        else:  # all
            data['target_department'] = None
            data['target_branch']     = None

        return data
