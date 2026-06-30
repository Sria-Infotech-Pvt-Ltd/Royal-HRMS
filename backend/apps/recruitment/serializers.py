import re

from rest_framework import serializers

from .models import Candidate, CandidateEmail, CandidateLog

_PHONE_RE = re.compile(r'^\+?[\d\s\-()\./]{7,20}$')


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
            'interview_date', 'interviewer', 'interviewer_name', 'interview_mode',
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
            'branch', 'interview_date', 'interviewer', 'interview_mode', 'notes',
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
        return value

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        if not value:
            raise serializers.ValidationError('Email address is required.')
        return value

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if len(value) > 20:
            raise serializers.ValidationError('Phone number must be 20 characters or fewer.')
        if not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
            )
        return value

    def validate_position_applied(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position applied is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Position applied must be 200 characters or fewer.')
        return value

    def validate_interview_mode(self, value: str) -> str:
        valid_modes = [choice[0] for choice in Candidate.MODE_CHOICES]
        if value and value not in valid_modes:
            raise serializers.ValidationError(
                f'Interview mode must be one of: {", ".join(valid_modes)}.'
            )
        return value

    def validate_notes(self, value: str) -> str:
        if value and len(value) > 2000:
            raise serializers.ValidationError('Notes must be 2000 characters or fewer.')
        return value


class CandidateUpdateSerializer(serializers.ModelSerializer):
    """Used for PUT / PATCH on an existing candidate.
    email is intentionally excluded — it cannot be changed after creation.
    """

    class Meta:
        model  = Candidate
        fields = [
            'name', 'phone', 'position_applied',
            'branch', 'interview_date', 'interviewer', 'interview_mode', 'notes',
            'referral_by',
        ]
        extra_kwargs = {
            'name':             {'required': True},
            'position_applied': {'required': True},
            # FK and date fields are optional — allow explicit null to clear
            'branch':         {'required': False, 'allow_null': True},
            'interview_date': {'required': False, 'allow_null': True},
            'interviewer':    {'required': False, 'allow_null': True},
            'referral_by':    {'required': False, 'allow_null': True},
            # Text fields are optional — allow blank to clear
            'phone':          {'required': False, 'allow_blank': True},
            'interview_mode': {'required': False, 'allow_blank': True},
            'notes':          {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Candidate name is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Candidate name must be 200 characters or fewer.')
        return value

    def validate_phone(self, value: str) -> str:
        if not value:
            return value
        value = value.strip()
        if len(value) > 20:
            raise serializers.ValidationError('Phone number must be 20 characters or fewer.')
        if not _PHONE_RE.match(value):
            raise serializers.ValidationError(
                'Enter a valid phone number (digits, spaces, +, -, ( ) allowed).'
            )
        return value

    def validate_position_applied(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Position applied is required.')
        if len(value) > 200:
            raise serializers.ValidationError('Position applied must be 200 characters or fewer.')
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

    def validate_notes(self, value: str) -> str:
        if value and len(value) > 2000:
            raise serializers.ValidationError('Notes must be 2000 characters or fewer.')
        return value
