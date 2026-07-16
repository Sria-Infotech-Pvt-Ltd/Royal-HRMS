import re
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import (
    Assessment, AssessmentItem, AssessmentSection, AssessmentSettings,
    CandidateAssignment, CandidateResponse,
)


def _to_embed_url(url: str) -> str:
    
    if not url:
        return url
    if 'youtube.com/embed/' in url:
        return url
    match = re.match(r'https?://youtu\.be/([A-Za-z0-9_-]+)', url)
    if match:
        return f'https://www.youtube.com/embed/{match.group(1)}'
    match = re.match(r'https?://(?:www\.)?youtube\.com/watch\?.*?v=([A-Za-z0-9_-]+)', url)
    if match:
        return f'https://www.youtube.com/embed/{match.group(1)}'
    return url


def _section_breakdown(assignment: CandidateAssignment) -> list:
    sections = list(assignment.assessment.sections.all())
    if not sections:
        return []
    quiz_items = list(
        assignment.assessment.items
            .filter(item_type=AssessmentItem.TYPE_QUIZ)
            .values('id', 'section_id')
    )
    correct_ids = frozenset(
        assignment.responses.filter(is_correct=True).values_list('item_id', flat=True)
    )
    section_map = {s.id: s for s in sections}
    section_items: dict = defaultdict(list)
    for item in quiz_items:
        sid = item['section_id']
        if sid and sid in section_map:
            section_items[sid].append(item['id'])

    result = []
    for section in sections:
        item_ids = section_items.get(section.id, [])
        if not item_ids:
            continue
        correct  = sum(1 for iid in item_ids if iid in correct_ids)
        achieved = round((correct / len(item_ids)) * section.score)
        result.append({
            'section_id':      str(section.id),
            'title':           section.title,
            'max_score':       section.score,
            'achieved_score':  achieved,
            'correct_answers': correct,
            'total_questions': len(item_ids),
            'percentage':      f'{round((achieved / section.score) * 100)}%' if section.score else 'N/A',
        })
    return result


# ─── Global settings ─────────────────────────────────────────────────────────

class AssessmentSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentSettings
        fields = ['default_pass_percentage', 'max_attempts', 'time_limit_mins', 'updated_at']

    def validate_default_pass_percentage(self, value):
        if not (1 <= value <= 100):
            raise serializers.ValidationError('Must be between 1 and 100.')
        return value

    def validate_max_attempts(self, value):
        if value < 0:
            raise serializers.ValidationError('Cannot be negative. Use 0 for unlimited.')
        return value

    def validate_time_limit_mins(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Time limit must be at least 1 minute, or leave blank for no limit.')
        return value


# ─── Section serializers ──────────────────────────────────────────────────────

class AssessmentSectionSerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model  = AssessmentSection
        fields = ['id', 'title', 'order', 'score', 'item_count', 'created_at']

    def get_item_count(self, obj: AssessmentSection) -> int:
        return obj.items.count()


class AssessmentSectionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentSection
        fields = ['title', 'order', 'score']

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('Title cannot be blank.')
        return value.strip()

    def validate_score(self, value):
        if value < 1:
            raise serializers.ValidationError('Section score must be at least 1.')
        return value


# ─── HR-facing serializers ────────────────────────────────────────────────────

class AssessmentItemSerializer(serializers.ModelSerializer):
    section_title = serializers.CharField(source='section.title', read_only=True, default=None)

    class Meta:
        model  = AssessmentItem
        fields = [
            'id', 'section_id', 'section_title', 'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option', 'created_at',
        ]


class AssessmentItemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = AssessmentItem
        fields = [
            'section', 'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_option',
        ]

    def validate(self, attrs):
        item_type = attrs.get('item_type')
        if item_type == AssessmentItem.TYPE_VIDEO:
            if not attrs.get('video_url'):
                raise serializers.ValidationError({'video_url': 'video_url is required for video items.'})
        elif item_type == AssessmentItem.TYPE_QUIZ:
            for field in ('question', 'option_a', 'option_b', 'correct_option'):
                if not attrs.get(field, '').strip():
                    raise serializers.ValidationError({field: f'{field} is required for quiz items.'})
            if attrs.get('correct_option', '') not in ('a', 'b', 'c', 'd'):
                raise serializers.ValidationError({'correct_option': 'Must be a, b, c, or d.'})
        # Ensure section belongs to the same assessment (validated in the view)
        return attrs


class AssessmentSerializer(serializers.ModelSerializer):
    sections                = AssessmentSectionSerializer(many=True, read_only=True)
    items                   = AssessmentItemSerializer(many=True, read_only=True)
    item_count              = serializers.SerializerMethodField()
    assigned_count          = serializers.SerializerMethodField()
    pending_count           = serializers.SerializerMethodField()
    in_progress_count       = serializers.SerializerMethodField()
    completed_count         = serializers.SerializerMethodField()
    candidates              = serializers.SerializerMethodField()
    effective_max_attempts  = serializers.SerializerMethodField()
    effective_time_limit_mins = serializers.SerializerMethodField()

    class Meta:
        model  = Assessment
        fields = [
            'id', 'title', 'description', 'is_active', 'is_default',
            'pass_percentage', 'max_attempts', 'time_limit_mins',
            'effective_max_attempts', 'effective_time_limit_mins',
            'item_count', 'assigned_count', 'pending_count',
            'in_progress_count', 'completed_count',
            'sections', 'candidates', 'items', 'created_at',
        ]

    def _settings(self) -> AssessmentSettings:
        return self.context.get('settings') or AssessmentSettings.load()

    def get_item_count(self, obj: Assessment) -> int:
        return obj.items.count()

    def get_assigned_count(self, obj: Assessment) -> int:
        return obj.assignments.count()

    def get_pending_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_PENDING).count()

    def get_in_progress_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_IN_PROGRESS).count()

    def get_completed_count(self, obj: Assessment) -> int:
        return obj.assignments.filter(status=CandidateAssignment.STATUS_COMPLETE).count()

    def get_effective_max_attempts(self, obj: Assessment) -> int:
        return obj.effective_max_attempts(self._settings())

    def get_effective_time_limit_mins(self, obj: Assessment):
        return obj.effective_time_limit_mins(self._settings())

    def get_candidates(self, obj: Assessment):
        return AssessmentCandidateSerializer(
            obj.assignments.all(), many=True, context={'assessment': obj},
        ).data


class AssessmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Assessment
        fields = [
            'title', 'description', 'is_active', 'is_default',
            'pass_percentage', 'max_attempts', 'time_limit_mins',
        ]

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError('Title cannot be blank.')
        return value.strip()

    def validate_pass_percentage(self, value):
        if not (1 <= value <= 100):
            raise serializers.ValidationError('pass_percentage must be between 1 and 100.')
        return value

    def validate_max_attempts(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError('Cannot be negative. Use 0 for unlimited.')
        return value

    def validate_time_limit_mins(self, value):
        if value is not None and value < 1:
            raise serializers.ValidationError('Time limit must be at least 1 minute.')
        return value


# ─── Portal-facing serializers (correct_option excluded) ─────────────────────

class PortalItemSerializer(serializers.ModelSerializer):
    video_url     = serializers.SerializerMethodField()
    section_id    = serializers.UUIDField(source='section.id',    read_only=True, default=None)
    section_title = serializers.CharField(source='section.title', read_only=True, default=None)

    class Meta:
        model  = AssessmentItem
        fields = [
            'id', 'section_id', 'section_title',
            'item_type', 'title', 'order',
            'video_url', 'duration_secs',
            'question', 'option_a', 'option_b', 'option_c', 'option_d',
        ]

    def get_video_url(self, obj: AssessmentItem) -> str:
        return _to_embed_url(obj.video_url)


class CandidateResponseSerializer(serializers.ModelSerializer):
    item_id   = serializers.UUIDField(source='item.id',        read_only=True)
    item_type = serializers.CharField(source='item.item_type', read_only=True)

    class Meta:
        model  = CandidateResponse
        fields = [
            'id', 'item_id', 'item_type',
            'is_watched', 'selected_option', 'is_correct',
            'score_awarded', 'responded_at',
        ]


class PortalAssignmentSerializer(serializers.ModelSerializer):
    assessment_title       = serializers.CharField(source='assessment.title',             read_only=True)
    pass_percentage        = serializers.IntegerField(source='assessment.pass_percentage', read_only=True)
    items                  = serializers.SerializerMethodField()
    responses              = CandidateResponseSerializer(many=True, read_only=True)
    total_items            = serializers.SerializerMethodField()
    completed_items        = serializers.SerializerMethodField()
    effective_max_attempts = serializers.SerializerMethodField()
    attempts_remaining     = serializers.SerializerMethodField()
    time_limit_mins        = serializers.SerializerMethodField()
    time_remaining_secs    = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id', 'assessment_title', 'pass_percentage', 'status',
            'score', 'max_score', 'total_items', 'completed_items',
            'attempt_count', 'effective_max_attempts', 'attempts_remaining',
            'started_at', 'time_limit_mins', 'time_remaining_secs',
            'deadline', 'completed_at', 'items', 'responses',
        ]

    def _settings(self) -> AssessmentSettings:
        return self.context.get('settings') or AssessmentSettings.load()

    def get_items(self, obj: CandidateAssignment):
        return PortalItemSerializer(obj.assessment.items.all(), many=True).data

    def get_total_items(self, obj: CandidateAssignment) -> int:
        return obj.assessment.items.count()

    def get_completed_items(self, obj: CandidateAssignment) -> int:
        all_items     = list(obj.assessment.items.all())
        video_ids     = {item.id for item in all_items if item.item_type == AssessmentItem.TYPE_VIDEO}
        quiz_ids      = {item.id for item in all_items if item.item_type == AssessmentItem.TYPE_QUIZ}
        all_responses = list(obj.responses.all())
        watched       = sum(1 for r in all_responses if r.item_id in video_ids and r.is_watched)
        answered      = sum(1 for r in all_responses if r.item_id in quiz_ids and r.selected_option)
        return watched + answered

    def get_effective_max_attempts(self, obj: CandidateAssignment) -> int:
        return obj.assessment.effective_max_attempts(self._settings())

    def get_attempts_remaining(self, obj: CandidateAssignment):
        effective = obj.assessment.effective_max_attempts(self._settings())
        if effective == 0:
            return None
        return max(0, effective - obj.attempt_count)

    def get_time_limit_mins(self, obj: CandidateAssignment):
        return obj.assessment.effective_time_limit_mins(self._settings())

    def get_time_remaining_secs(self, obj: CandidateAssignment):
        if obj.started_at is None:
            return None
        limit = obj.assessment.effective_time_limit_mins(self._settings())
        if limit is None:
            return None
        remaining = (obj.started_at + timedelta(minutes=limit) - timezone.now()).total_seconds()
        return max(0, int(remaining))


# ─── HR results serializer ────────────────────────────────────────────────────

class ResultsAssignmentSerializer(serializers.ModelSerializer):
    assessment_title   = serializers.CharField(source='assessment.title',             read_only=True)
    pass_percentage    = serializers.IntegerField(source='assessment.pass_percentage', read_only=True)
    responses          = CandidateResponseSerializer(many=True, read_only=True)
    total_items        = serializers.SerializerMethodField()
    score_percentage   = serializers.SerializerMethodField()
    sections_breakdown = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id', 'assessment_title', 'pass_percentage', 'status',
            'score', 'max_score', 'total_items', 'score_percentage',
            'sections_breakdown',
            'attempt_count', 'completed_at', 'responses',
        ]

    def get_total_items(self, obj: CandidateAssignment) -> int:
        return obj.assessment.items.count()

    def get_score_percentage(self, obj: CandidateAssignment) -> str:
        if obj.max_score == 0:
            return 'N/A'
        return f'{round((obj.score / obj.max_score) * 100)}%'

    def get_sections_breakdown(self, obj: CandidateAssignment) -> list:
        return _section_breakdown(obj)


# ─── HR: per-assessment candidate participation list ─────────────────────────

class AssessmentCandidateSerializer(serializers.ModelSerializer):
    assignee_id        = serializers.SerializerMethodField()
    assignee_name      = serializers.SerializerMethodField()
    assignee_email     = serializers.SerializerMethodField()
    assignee_type      = serializers.SerializerMethodField()
    total_questions    = serializers.IntegerField(source='max_score', read_only=True)
    achieved_score     = serializers.IntegerField(source='score',     read_only=True)
    score_percentage   = serializers.SerializerMethodField()
    pass_percentage    = serializers.SerializerMethodField()
    passed             = serializers.SerializerMethodField()
    sections_breakdown = serializers.SerializerMethodField()

    class Meta:
        model  = CandidateAssignment
        fields = [
            'id',
            'assignee_type', 'assignee_id', 'assignee_name', 'assignee_email',
            'status', 'attempt_count',
            'total_questions', 'achieved_score',
            'score_percentage', 'pass_percentage', 'passed',
            'sections_breakdown',
            'deadline', 'completed_at', 'created_at',
        ]

    def get_assignee_type(self, obj: CandidateAssignment) -> str:
        return 'candidate' if obj.candidate_id else 'employee'

    def get_assignee_id(self, obj: CandidateAssignment):
        if obj.candidate_id:
            return obj.candidate_id
        return str(obj.employee_id) if obj.employee_id else None

    def get_assignee_name(self, obj: CandidateAssignment) -> str:
        if obj.candidate_id and obj.candidate:
            return obj.candidate.name
        if obj.employee_id and obj.employee:
            return obj.employee.full_name or obj.employee.email
        return ''

    def get_assignee_email(self, obj: CandidateAssignment) -> str:
        if obj.candidate_id and obj.candidate:
            return obj.candidate.email
        if obj.employee_id and obj.employee:
            return obj.employee.email
        return ''

    def get_score_percentage(self, obj: CandidateAssignment) -> str:
        if obj.max_score == 0:
            return 'N/A'
        return f'{round((obj.score / obj.max_score) * 100)}%'

    def get_pass_percentage(self, obj: CandidateAssignment) -> int:
        assessment = self.context.get('assessment') or obj.assessment
        return assessment.pass_percentage

    def get_passed(self, obj: CandidateAssignment) -> bool:
        if obj.status != CandidateAssignment.STATUS_COMPLETE or obj.max_score == 0:
            return False
        assessment = self.context.get('assessment') or obj.assessment
        return round((obj.score / obj.max_score) * 100) >= assessment.pass_percentage

    def get_sections_breakdown(self, obj: CandidateAssignment) -> list:
        if obj.status != CandidateAssignment.STATUS_COMPLETE:
            return []
        return _section_breakdown(obj)
