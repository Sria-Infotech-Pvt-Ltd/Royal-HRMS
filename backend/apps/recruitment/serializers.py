import re
from datetime import date

from django.utils import timezone
from rest_framework import serializers

from .models import Candidate, CandidateEmail, CandidateLog, ReferralBonus, ReferralRule

_PHONE_RE    = re.compile(r'^\+?[0-9]{10,15}$')
_NAME_RE     = re.compile(r"^[A-Za-z][A-Za-z .'-]*$")
_POSITION_RE = re.compile(r"^[A-Za-z][A-Za-z .&/-]*$")


class CandidateLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CandidateLog
        fields = ['id', 'log_type', 'title', 'description', 'created_at']


class CandidateEmailSerializer(serializers.ModelSerializer):
    sent_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateEmail
        fields = ['id', 'template_used', 'subject', 'to_email', 'status', 'sent_by_name', 'sent_at',
                  'candidate', 'candidate_name', 'candidate_position']

    def get_sent_by_name(self, obj):
        if obj.sent_by:
            return obj.sent_by.full_name or obj.sent_by.email
        return ''

    # Extra read-only fields that join candidate data for the email logs page
    candidate_name     = serializers.CharField(source='candidate.name',             read_only=True)
    candidate_position = serializers.CharField(source='candidate.position_applied', read_only=True)


class CandidateListSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()
    added_by_name    = serializers.SerializerMethodField()
    referral_by_name = serializers.SerializerMethodField()
    branch_name      = serializers.SerializerMethodField()

    class Meta:
        model  = Candidate
        fields = [
            'id', 'name', 'email', 'phone', 'position_applied',
            'branch', 'branch_name',
            'interview_date', 'interview_time', 'interviewer', 'interviewer_name',
            'interview_mode', 'meeting_link',
            'notes', 'status', 'referral_by', 'referral_by_name',
            'details_filled', 'hr_approved', 'portal_credentials_sent',
            'added_by_name', 'created_at', 'updated_at',
        ]

    def get_interviewer_name(self, obj):
        if obj.interviewer:
            return obj.interviewer.full_name or obj.interviewer.email
        return ''

    def get_added_by_name(self, obj):
        if obj.added_by:
            return obj.added_by.full_name or obj.added_by.email
        return ''

    def get_referral_by_name(self, obj):
        if obj.referral_by:
            return obj.referral_by.full_name or obj.referral_by.email
        return ''

    def get_branch_name(self, obj):
        return obj.branch.branch_name if obj.branch else ''


class CandidateDetailSerializer(CandidateListSerializer):
    logs = CandidateLogSerializer(many=True, read_only=True)

    class Meta(CandidateListSerializer.Meta):
        fields = CandidateListSerializer.Meta.fields + ['logs']


class CandidateCreateSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(required=True, max_length=254)

    class Meta:
        model  = Candidate
        fields = [
            'name', 'email', 'phone', 'position_applied',
            'branch', 'interview_date', 'interview_time', 'interviewer',
            'interview_mode', 'meeting_link', 'notes',
        ]
        extra_kwargs = {
            'name':             {'required': True},
            'position_applied': {'required': True},
        }

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Candidate name is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Candidate name must be 200 characters or fewer.')
        if not _NAME_RE.match(value):
            raise serializers.ValidationError(
                'Candidate name can only contain letters, spaces, apostrophes, hyphens, and periods — no numbers or special characters.'
            )
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError('Email address is required.')
        existing = Candidate.objects.filter(email__iexact=value).first()
        if existing:
            raise serializers.ValidationError(
                f'A candidate with this email already exists: {existing.name} '
                f'({existing.get_status_display()} for {existing.position_applied}).'
            )
        return value

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (10 to 15 digits, optionally starting with +). '
                'Letters and special characters are not allowed.'
            )
        return value

    def validate_position_applied(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position applied is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Position applied must be 200 characters or fewer.')
        if not _POSITION_RE.match(value):
            raise serializers.ValidationError(
                'Position applied can only contain letters, spaces, and & / . - — no numbers or other special characters.'
            )
        return value

    def validate_interview_mode(self, value: str) -> str:
        valid_modes = [choice[0] for choice in Candidate.MODE_CHOICES]
        if value and value not in valid_modes:
            raise serializers.ValidationError(
                f'Interview mode must be one of: {", ".join(valid_modes)}.'
            )
        return value

    def validate_interview_date(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError('Interview date cannot be in the past.')
        return value

    def validate_notes(self, value: str) -> str:
        if value and len(value) > 2000:
            raise serializers.ValidationError('Notes must be 2000 characters or fewer.')
        return value


class ReferralSubmitSerializer(CandidateCreateSerializer):
    """
    Used by ReferralListCreateView.post — any authenticated employee can refer
    a candidate, but only with these fields. branch/interview_date/interviewer/
    interview_mode are HR-only concerns and must never be settable by a referrer.
    """
    class Meta(CandidateCreateSerializer.Meta):
        fields = ['name', 'email', 'phone', 'position_applied', 'notes']


# ── Bulk Import ───────────────────────────────────────────────────────────────

_BULK_MODE_ALIASES = {
    'in person':  'in_person',
    'in-person':  'in_person',
    'inperson':   'in_person',
    'in_person':  'in_person',
    'video':      'video_call',
    'video call': 'video_call',
    'video_call': 'video_call',
    'videocall':  'video_call',
    'online':     'video_call',
    'phone':      'phone',
    'phone call': 'phone',
    'phone_call': 'phone',
}

_VALID_IMPORT_MODES = frozenset(choice[0] for choice in Candidate.MODE_CHOICES)


class CandidateBulkImportRowSerializer(serializers.Serializer):
    """Validates one row from a bulk-import CSV/XLSX file.

    Branch resolution happens in the view (pre-loaded once for the whole batch,
    not per-row), so branch_name is kept as a plain CharField here.
    """

    name             = serializers.CharField(max_length=200)
    email            = serializers.EmailField()
    phone            = serializers.CharField(max_length=20, required=False,
                                             allow_blank=True, default='')
    position_applied = serializers.CharField(max_length=200)
    branch_name      = serializers.CharField()
    interview_date   = serializers.DateField(
        required=False, allow_null=True, default=None,
        input_formats=['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', 'iso-8601'],
    )
    interview_mode   = serializers.CharField(required=False, allow_blank=True, default='')
    notes            = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Full name is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Name must be 200 characters or fewer.')
        return value

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_phone(self, value: str) -> str:
        value = value.strip()
        if value and not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
            )
        return value

    def validate_interview_mode(self, value: str) -> str:
        if not value:
            return value
        normalised = _BULK_MODE_ALIASES.get(value.strip().lower(), value.strip().lower())
        if normalised not in _VALID_IMPORT_MODES:
            raise serializers.ValidationError(
                f'Invalid interview mode "{value}". '
                f'Allowed: {", ".join(sorted(_VALID_IMPORT_MODES))}.'
            )
        return normalised

    def validate_interview_date(self, value) -> object:
        return value

    def validate_notes(self, value: str) -> str:
        if value and len(value) > 2000:
            raise serializers.ValidationError('Notes must be 2000 characters or fewer.')
        return value


class ReferralRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ReferralRule
        fields = ['id', 'icon', 'title', 'body', 'order', 'is_active', 'created_at', 'updated_at']
        extra_kwargs = {
            'icon':  {'required': True},
            'title': {'required': True},
            'body':  {'required': True},
        }


class ReferralBonusSerializer(serializers.ModelSerializer):
    referrer_name      = serializers.SerializerMethodField()
    referrer_id        = serializers.SerializerMethodField()
    candidate_name     = serializers.SerializerMethodField()
    candidate_position = serializers.SerializerMethodField()
    approved_by_name   = serializers.SerializerMethodField()
    paid_by_name       = serializers.SerializerMethodField()
    status_display     = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model  = ReferralBonus
        fields = [
            'id', 'candidate', 'candidate_name', 'candidate_position',
            'referrer', 'referrer_name', 'referrer_id',
            'bonus_amount', 'status', 'status_display', 'notes',
            'approved_by', 'approved_by_name', 'approved_at',
            'paid_by', 'paid_by_name', 'paid_at',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'approved_by', 'approved_at', 'paid_by', 'paid_at',
            'created_at', 'updated_at',
        ]

    def get_referrer_name(self, obj):
        return obj.referrer.full_name or obj.referrer.email

    def get_referrer_id(self, obj):
        return obj.referrer.employee_id or ''

    def get_candidate_name(self, obj):
        return obj.candidate.name

    def get_candidate_position(self, obj):
        return obj.candidate.position_applied

    def get_approved_by_name(self, obj):
        return (obj.approved_by.full_name or obj.approved_by.email) if obj.approved_by else ''

    def get_paid_by_name(self, obj):
        return (obj.paid_by.full_name or obj.paid_by.email) if obj.paid_by else ''


class CandidateUpdateSerializer(serializers.ModelSerializer):
    """Used for PUT / PATCH on an existing candidate.
    email is intentionally excluded — it cannot be changed after creation.
    """

    class Meta:
        model  = Candidate
        fields = [
            'name', 'phone', 'position_applied',
            'branch', 'interview_date', 'interview_time', 'interviewer',
            'interview_mode', 'meeting_link', 'notes',
            'referral_by',
        ]
        extra_kwargs = {
            'name':             {'required': True},
            'position_applied': {'required': True},
            # FK and date fields are optional — allow explicit null to clear
            'branch':         {'required': False, 'allow_null': True},
            'interview_date': {'required': False, 'allow_null': True},
            'interview_time': {'required': False, 'allow_null': True},
            'interviewer':    {'required': False, 'allow_null': True},
            'referral_by':    {'required': False, 'allow_null': True},
            # Text fields are optional — allow blank to clear
            'phone':          {'required': False, 'allow_blank': True},
            'interview_mode': {'required': False, 'allow_blank': True},
            'meeting_link':   {'required': False, 'allow_blank': True},
            'notes':          {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Candidate name is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Candidate name must be 200 characters or fewer.')
        if not _NAME_RE.match(value):
            raise serializers.ValidationError(
                'Candidate name can only contain letters, spaces, apostrophes, hyphens, and periods — no numbers or special characters.'
            )
        return value

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (10 to 15 digits, optionally starting with +). '
                'Letters and special characters are not allowed.'
            )
        return value

    def validate_position_applied(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position applied is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Position applied must be 200 characters or fewer.')
        if not _POSITION_RE.match(value):
            raise serializers.ValidationError(
                'Position applied can only contain letters, spaces, and & / . - — no numbers or other special characters.'
            )
        return value

    def validate_interview_mode(self, value: str) -> str:
        if not value:
            return value
        valid_modes = [choice[0] for choice in Candidate.MODE_CHOICES]
        if value not in valid_modes:
            raise serializers.ValidationError(
                f'Interview mode must be one of: {", ".join(valid_modes)}.'
            )
        return value

    def validate_interview_date(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError('Interview date cannot be in the past.')
        return value

    def validate_notes(self, value: str) -> str:
        if value and len(value) > 2000:
            raise serializers.ValidationError('Notes must be 2000 characters or fewer.')
        return value
